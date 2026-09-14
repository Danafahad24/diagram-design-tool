"""Server-side Iconify adapter: open icon search, no API key, no account.

Two endpoints on the public Iconify API are reached, and nothing else:

    GET /search?query=<text>&limit=<n>   -> candidate icon ids
    GET /<prefix>/<name>.svg            -> one icon's SVG

An icon id is Iconify's ``prefix:name`` (``logos:java``, ``lucide:database``).
The model picks one with ``search_diagram_icons`` and puts it on an element as
``icon_id``; ``hydrate_diagram`` resolves it to an inline ``data:`` URI **on the
server**, so the browser never talks to Iconify and a generated diagram carries
no external references.

Why fetched SVG is sanitized even though it is only ever used as an image:
browsers do not run script in SVG-as-image mode, so this is defence in depth
rather than the only barrier. The rewrite that is *not* optional is the size
one — Iconify serves ``width="1em" height="1em"``, which has no meaning in a
data URI with no font context, so every icon has to be given real pixels
before it can rasterize for the Word/PowerPoint export.

Lucide is NOT fetched for the built-in element types (`server`, `database`,
`cloud`, `api`, …): those draw from the copy of `@iconify-json/lucide` compiled
into `assets/maxgraph.bundle.js`, offline and with no request at all. This
module is for everything that is not one of those — brand and technology logos
above all.
"""

import base64
import os
import re
import threading
from urllib.parse import quote, urlsplit

import httpx
from lxml import etree

from canvas_diagram.models import CanvasElementType


DEFAULT_API_BASE = "https://api.iconify.design"

# Only the official host, unless an operator deliberately points this at their
# own Iconify instance. A hostname that is not this one and was not configured
# is refused rather than followed.
OFFICIAL_HOST = "api.iconify.design"

# Brand/technology logo sets, in the order a logo request should prefer them.
# `logos` is full-colour artwork, `devicon` covers developer tooling, and
# `simple-icons` is the monochrome fallback that has nearly every brand.
BRAND_COLLECTIONS = ("logos", "devicon", "simple-icons")

# Element types that already draw a bundled Lucide icon with no network call.
# Surfaced in search results so the model prefers the offline shape when one
# fits, instead of fetching a near-identical icon.
BUILTIN_ICON_TYPES: dict[str, tuple[str, ...]] = {
    "user": ("user", "person", "customer", "client", "actor", "employee"),
    "actor": ("actor", "role", "stakeholder", "persona"),
    "server": ("server", "host", "vm", "machine", "backend", "node"),
    "database": ("database", "db", "sql", "datastore", "storage", "table"),
    "cloud": ("cloud", "saas", "internet", "hosting"),
    "api": ("api", "endpoint", "rest", "graphql", "interface"),
    "service": ("service", "microservice", "component", "module"),
    "queue": ("queue", "broker", "message", "topic", "stream", "layers"),
    "container": ("container", "pod", "box"),
    "code": ("code", "script", "source", "repository", "function"),
    "document": ("document", "file", "report", "doc", "paper", "page"),
}

# Iconify's own id grammar: lowercase alphanumerics and hyphens on both sides
# of a single colon. Anything else never reaches a URL.
ICON_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$")

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# Elements that can execute or reach out, dropped wholesale.
FORBIDDEN_TAGS = {"script", "foreignObject", "iframe", "audio", "video", "set"}

# The intrinsic size stamped onto every icon. The artwork stays vector — this
# only replaces the meaningless `1em` so a rasterizer has somewhere to start.
ICON_PIXELS = 256

MAX_SVG_BYTES = 512_000
MAX_SEARCH_LIMIT = 30

# Iconify clamps `limit` up to 32; asking for less is pointless, so ask for a
# useful pool and slice it here.
API_SEARCH_POOL = 64


class IconifyError(RuntimeError):
    """Iconify could not be reached, or returned nothing usable."""


class IconNotFound(IconifyError):
    """The requested icon id does not exist. Never substitute another icon."""


def _api_base() -> str:
    base = (os.getenv("ICONIFY_API_BASE") or DEFAULT_API_BASE).rstrip("/")
    parsed = urlsplit(base)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise IconifyError("ICONIFY_API_BASE is not a valid http(s) URL.")

    if parsed.username or parsed.password:
        raise IconifyError("ICONIFY_API_BASE must not carry credentials.")

    # The default must be the official host over TLS; an operator who sets the
    # variable has taken responsibility for whatever they pointed it at.
    if not os.getenv("ICONIFY_API_BASE"):
        if parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST:
            raise IconifyError("Refusing a non-official default Iconify host.")

    return base


def _strip_external_css(text: str) -> str:
    """Remove @import and url(http…) from an inline <style>."""
    text = re.sub(r"@import[^;]*;?", "", text, flags=re.I)
    return re.sub(r"url\(\s*['\"]?\s*(?:https?:)?//[^)]*\)", "none", text, flags=re.I)


def sanitize_svg(data: bytes, pixels: int = ICON_PIXELS) -> bytes:
    """Parse, strip anything active or outbound, and stamp a real size.

    Raises IconifyError if the payload is not parseable SVG.
    """

    if not data or len(data) > MAX_SVG_BYTES:
        raise IconifyError("Icon SVG is empty or exceeds the size limit.")

    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )

    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as exc:
        raise IconifyError("Iconify returned something that is not valid SVG.") from exc

    if etree.QName(root).localname != "svg":
        raise IconifyError("Iconify returned a document whose root is not <svg>.")

    for node in list(root.iter()):
        if not isinstance(node.tag, str):
            # Comments and processing instructions carry nothing we want.
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
            continue

        local = etree.QName(node).localname

        if local in FORBIDDEN_TAGS:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
            continue

        if local == "style" and node.text:
            node.text = _strip_external_css(node.text)

        for name, value in list(node.attrib.items()):
            bare = etree.QName(name).localname if name.startswith("{") else name

            # Event handlers, and anything that would fetch.
            if bare.lower().startswith("on"):
                del node.attrib[name]
                continue

            if bare in ("href", "src"):
                if not value.startswith(("#", "data:")):
                    # An <image>/<use> whose only source was external is inert
                    # once stripped; drop the element rather than leave a stub.
                    del node.attrib[name]
                    if local in ("image", "use"):
                        parent = node.getparent()
                        if parent is not None:
                            parent.remove(node)
                            break
                continue

            if "url(" in value.lower() and re.search(r"url\(\s*['\"]?\s*(?:https?:)?//", value, re.I):
                del node.attrib[name]

    # `1em` is unresolvable in a data URI, so give the icon real pixels while
    # keeping the viewBox that defines its aspect ratio.
    if not root.get("viewBox"):
        root.set("viewBox", f"0 0 {pixels} {pixels}")

    root.set("width", str(pixels))
    root.set("height", str(pixels))

    # Only stamp a literal xmlns when the source had none — lxml serializes a
    # real namespace on its own, and setting both emits `xmlns` twice, which is
    # not well-formed XML and fails to parse as an image.
    if root.tag == "svg":
        root.set("xmlns", SVG_NS)

    return etree.tostring(root, xml_declaration=False)


def to_data_uri(svg: bytes) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")


class IconifyClient:
    """Small cached client over the two Iconify endpoints this needs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._icons: dict[str, tuple[str, str]] = {}
        self._collections: dict[str, dict] = {}

    # -- transport ----------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        url = _api_base() + path
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client:
                response = client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise IconifyError(
                "Could not reach the Iconify icon service; check outbound "
                "network access from Workbench."
            ) from exc

        if response.status_code == 404:
            raise IconNotFound("That icon id does not exist on Iconify.")

        if response.status_code >= 400:
            raise IconifyError(
                f"Iconify answered {response.status_code}; the icon service is "
                f"unavailable right now."
            )

        return response

    # -- metadata -----------------------------------------------------------

    def collection(self, prefix: str) -> dict:
        with self._lock:
            cached = self._collections.get(prefix)
        if cached is not None:
            return cached

        try:
            data = self._get("/collections", {"prefix": prefix}).json()
            meta = data.get(prefix) or {}
        except (IconifyError, ValueError):
            meta = {}

        with self._lock:
            self._collections[prefix] = meta
        return meta

    # -- search -------------------------------------------------------------

    def _raw_search(self, query: str, prefixes: str | None = None) -> dict:
        params: dict[str, str | int] = {"query": query, "limit": API_SEARCH_POOL}
        if prefixes:
            params["prefixes"] = prefixes

        try:
            return self._get("/search", params).json()
        except ValueError as exc:
            raise IconifyError("Iconify returned a malformed search response.") from exc

    def search(self, query: str, limit: int = 12) -> dict:
        """Search Iconify, brand collections first, and describe each hit."""

        limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))

        branded = self._raw_search(query, ",".join(BRAND_COLLECTIONS))
        general = self._raw_search(query)

        collections: dict[str, dict] = {}
        collections.update(general.get("collections") or {})
        collections.update(branded.get("collections") or {})

        ordered: list[str] = []
        for icon_id in list(branded.get("icons") or []) + list(general.get("icons") or []):
            if icon_id not in ordered and ICON_ID_RE.match(icon_id):
                ordered.append(icon_id)

        base = _api_base()
        results = []
        for icon_id in ordered[:limit]:
            prefix, _, name = icon_id.partition(":")
            meta = collections.get(prefix) or {}
            licence = (meta.get("license") or {}).get("title") or "see collection"
            results.append(
                {
                    "icon_id": icon_id,
                    "collection": meta.get("name") or prefix,
                    "license": licence,
                    # True = the icon carries its own brand colours; False = a
                    # monochrome glyph that takes the element's stroke colour.
                    "colored": bool(meta.get("palette")),
                    "preview_url": f"{base}/{quote(prefix)}/{quote(name)}.svg",
                }
            )

        return {
            "query": query,
            "results": results,
            "builtin_types": self.builtin_matches(query),
        }

    @staticmethod
    def builtin_matches(query: str) -> list[str]:
        """Built-in element types whose bundled Lucide icon already fits."""
        words = set(re.findall(r"[a-z]+", query.lower()))
        return [
            element_type
            for element_type, terms in BUILTIN_ICON_TYPES.items()
            if words & set(terms)
        ]

    # -- fetch --------------------------------------------------------------

    def image(self, icon_id: str, color: str | None = None) -> tuple[str, str]:
        """Return (data URI, attribution) for one icon id."""

        icon_id = (icon_id or "").strip().lower()

        if not ICON_ID_RE.match(icon_id):
            raise IconifyError(
                f"'{icon_id}' is not a valid Iconify id. Expected "
                f"'collection:name', for example 'logos:java'."
            )

        cache_key = f"{icon_id}|{color or ''}"
        with self._lock:
            cached = self._icons.get(cache_key)
        if cached is not None:
            return cached

        prefix, _, name = icon_id.partition(":")
        params = {"color": color} if color else None
        response = self._get(f"/{quote(prefix)}/{quote(name)}.svg", params)

        body = response.content
        # Iconify answers 200 with a tiny "404" body for some malformed ids.
        if len(body) < 32 or b"<svg" not in body[:512]:
            raise IconNotFound(f"Iconify has no icon '{icon_id}'.")

        svg = sanitize_svg(body)

        meta = self.collection(prefix)
        author = (meta.get("author") or {}).get("name") or prefix
        licence = (meta.get("license") or {}).get("title") or "see collection"
        attribution = (
            f"{icon_id} — {meta.get('name') or prefix} by {author} "
            f"({licence}) via Iconify"
        )

        resolved = (to_data_uri(svg), attribution)
        with self._lock:
            self._icons[cache_key] = resolved
        return resolved


iconify = IconifyClient()


def hydrate_diagram(body):
    """Resolve every element's `icon_id` into an inline image, server-side."""

    result = body.model_copy(deep=True)
    resolved: dict[str, tuple[str, str]] = {}

    for element in result.elements:
        if element.icon_id:
            if element.icon_id not in resolved:
                resolved[element.icon_id] = iconify.image(
                    element.icon_id,
                    (element.style.stroke if element.style else None),
                )
            element.image_data, element.attribution = resolved[element.icon_id]
            element.type = CanvasElementType.IMAGE

        elif element.type == "image" and not element.image_data:
            raise ValueError("Image elements require image_data or icon_id.")

    return result
