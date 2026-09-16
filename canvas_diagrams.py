"""The Canvas Diagram Designer: the editable maxGraph editor and its exports.

Three tools reach the model — `create_canvas_diagram` (returns the editor as a
Rich UI), `search_diagram_icons` (open Iconify lookup) and
`export_canvas_office` (headless render into DOCX/PPTX) — plus one unregistered
asset route that serves the compiled maxGraph bundle to the browser.
"""

import asyncio
import base64
import binascii
import re
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from uuid import uuid4
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

import config
from canvas_diagram.editor import build_canvas_editor_html
from canvas_diagram.iconify import IconifyError, hydrate_diagram, iconify
from canvas_diagram.models import CreateCanvasDiagramBody
from canvas_diagram.office import insert_diagram_png, render_diagram_png
from security.identity import owner_for
from workspace_agent.common import links
from workspace_agent.common.minio import get_default_clients, upload_bytes
from workspace_agent.common.ownership import document_key


router = APIRouter()


MAX_DIAGRAM_ELEMENTS = 500
MAX_DIAGRAM_CONNECTIONS = 1000
MAX_DIAGRAM_EXTENT = 20000


def _check_diagram_limits(diagram: CreateCanvasDiagramBody) -> None:
    """Reject diagrams too large to render or edit sensibly.

    Applied to every entry point that builds a diagram (interactive editor
    and office export alike) so the limits can't be bypassed by calling one
    tool instead of the other.
    """

    if (
        len(diagram.elements) > MAX_DIAGRAM_ELEMENTS
        or len(diagram.connections) > MAX_DIAGRAM_CONNECTIONS
    ):
        raise HTTPException(
            422,
            f"Diagram exceeds {MAX_DIAGRAM_ELEMENTS} elements or "
            f"{MAX_DIAGRAM_CONNECTIONS} connections.",
        )

    if any(
        max(abs(e.x), abs(e.y), e.width, e.height) > MAX_DIAGRAM_EXTENT
        for e in diagram.elements
    ):
        raise HTTPException(
            422, f"Diagram geometry must stay within {MAX_DIAGRAM_EXTENT} units."
        )


# Per-user sliding-window limits. export_canvas_office already has a global
# semaphore bounding concurrent renders; these bound how often any one user
# can call the cheaper, unbounded-concurrency tools.
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMITS = {
    "create_canvas_diagram": 20,
    "search_diagram_icons": 30,
}

_rate_limit_lock = threading.Lock()
_rate_limit_hits: dict[str, deque[float]] = defaultdict(deque)


def _enforce_rate_limit(bucket: str, user_id: str) -> None:
    limit = RATE_LIMITS[bucket]
    key = f"{bucket}:{user_id}"
    now = time.monotonic()

    with _rate_limit_lock:
        hits = _rate_limit_hits[key]
        while hits and now - hits[0] > RATE_LIMIT_WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= limit:
            raise HTTPException(
                429,
                f"Too many requests; limit is {limit} per "
                f"{RATE_LIMIT_WINDOW_SECONDS}s. Try again shortly.",
            )

        hits.append(now)


# The compiled bundle from canvas_diagram/frontend/src/index.js. editor.py
# pins the version it expects (MAXGRAPH_ASSET_VERSION) and the page refuses to
# start on a mismatch, so this file is a build artefact, not a vendored copy.
MAXGRAPH_JS_PATH = (
    Path(__file__).resolve().parents[1]
    / "canvas_diagram"
    / "assets"
    / "maxgraph.bundle.js"
)


@router.get(
    "/canvas-assets/maxgraph.bundle.js",
    include_in_schema=False,
)
def get_canvas_maxgraph_js() -> FileResponse:
    """Serve the local maxGraph browser bundle."""

    return FileResponse(
        MAXGRAPH_JS_PATH,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


@router.post(
    "/tools/create_canvas_diagram",
    tags=["diagrams"],
    operation_id="create_canvas_diagram",
    response_class=HTMLResponse,
    summary="Create an editable general-purpose diagram",
    description=(
        "Create an editable general-purpose diagram. First identify the requested "
        "diagram type and follow the correct conventions for that type. Do not turn "
        "every request into an architecture diagram and do not mix diagram notations "
        "unless the user explicitly asks for a hybrid diagram. "

        "USE CASE DIAGRAM: use proper UML use-case notation. Actors belong outside "
        "the system boundary. Use cases belong inside the system boundary and should "
        "be represented as use-case ovals. Use actor-to-use-case associations and "
        "include/extend relationships only when appropriate. "

        "SWIMLANE DIAGRAM: create real labeled lanes for roles, teams, systems, or "
        "participants. Every activity must be placed inside the lane responsible for "
        "that activity. Show process flow between lanes and use start/end, task, and "
        "decision shapes where appropriate. A row of components is not a swimlane. "

        "FLOWCHART: use start/end shapes, process shapes, input/output shapes, and "
        "decision diamonds correctly. Label decision branches such as Yes/No or "
        "Approved/Rejected. "

        "ER DIAGRAM: use entity/table-style nodes with attributes, primary keys, "
        "foreign keys, relationships, and cardinality where applicable. Do not render "
        "an ER diagram as a workflow. "

        "UML CLASS DIAGRAM: use class compartments for class name, attributes, and "
        "methods. Use association, inheritance, aggregation, and composition correctly "
        "when required. "

        "SEQUENCE DIAGRAM: place participants across the top, use lifelines, and show "
        "messages in chronological order from top to bottom. "

        "ACTIVITY DIAGRAM: use start/end nodes, actions, decision nodes, branches, "
        "merges, and control flow according to the process. "

        "ARCHITECTURE DIAGRAM: use technical components such as services, APIs, "
        "databases, queues, models, storage, and external systems with logical "
        "connections between them. "

        "If the user explicitly names a diagram type, preserve that type even if the "
        "content could also be shown using another diagram style. If the user does "
        "not specify a type, infer the most appropriate one from the request. "

        "Respond in English unless the user requests another language. After rendering, "
        "tell the user they can edit the diagram with the expand button at the top right. "

        "Built-in types (server, database, cloud, api, user, service, queue, container, "
        "code, document) already draw their own icon offline — use those first. For a "
        "brand or technology logo the user named, call search_diagram_icons and copy "
        "an icon_id from its results onto an element. Never invent an icon_id. "
        "For Word or PowerPoint use export_canvas_office. "
    ),
)
def create_canvas_diagram(
    body: CreateCanvasDiagramBody,
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> HTMLResponse:
    """Create and render an editable canvas diagram."""

    config.check_auth(x_api_key)

    # Validate/resolve the Open WebUI identity.
    user_id, _owner = owner_for(request)
    _enforce_rate_limit("create_canvas_diagram", user_id)

    _check_diagram_limits(body)

    try:
        hydrated = hydrate_diagram(body)
    except IconifyError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    html = build_canvas_editor_html(hydrated)

    return HTMLResponse(
        content=html,
        headers={
            "Content-Disposition": "inline",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


class SearchDiagramIconsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=12, ge=1, le=30)


@router.post(
    "/tools/search_diagram_icons",
    tags=["diagrams"],
    operation_id="search_diagram_icons",
    description=(
        "Search the open Iconify catalogue for an icon or brand/technology logo. "
        "Search with the plain thing the user named — 'java', 'docker', 'aws', "
        "'postgresql', 'kubernetes', 'shopping cart' — not an id: the user never "
        "supplies an icon_id, you find it here. Copy an `icon_id` from the results "
        "verbatim onto an element's `icon_id` field. Brand sets (logos, devicon, "
        "simple-icons) are returned first; `colored: true` means the icon carries "
        "its own brand colours. If `builtin_types` is non-empty, one of those "
        "element types already draws that symbol offline — prefer it over fetching. "
        "If `results` is empty, TELL THE USER no matching icon was found and use a "
        "plain labelled shape instead; never substitute an unrelated icon and never "
        "guess an icon_id that was not returned here."
    ),
)
def search_diagram_icons(
    body: SearchDiagramIconsBody,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    config.check_auth(x_api_key)
    user_id, _owner = owner_for(request)
    _enforce_rate_limit("search_diagram_icons", user_id)

    try:
        found = iconify.search(body.query, body.limit)
    except IconifyError as exc:
        raise HTTPException(503, str(exc)) from exc

    if not found["results"]:
        found["message"] = (
            f"No icon on Iconify matched '{body.query}'. Tell the user plainly "
            f"that no matching icon was found, and use a labelled shape instead. "
            f"Do not substitute a different or unrelated icon."
        )

    return found


class DiagramInsertLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position: Literal["end", "start", "after_heading", "after_slide"] = "end"
    heading: str | None = Field(
        default=None,
        max_length=300,
        description="docx, position=after_heading: text of the heading/paragraph to insert after.",
    )
    slide_index: int | None = Field(
        default=None,
        ge=0,
        description="pptx, position=after_slide: 0-based index of an existing slide to insert after.",
    )
    slide_title: str | None = Field(
        default=None,
        max_length=300,
        description="pptx, position=after_slide: alternative to slide_index, matched against a slide's title text.",
    )


class ExportCanvasOfficeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    diagram: CreateCanvasDiagramBody
    format: Literal["docx", "pptx"]
    existing_document_base64: str | None = Field(
        default=None,
        max_length=27000000,
        description=(
            "Optional existing DOCX/PPTX bytes encoded by the file/tool adapter, not "
            "invented by the model. Appends on a new page/slide and returns a new file."
        ),
    )
    location: DiagramInsertLocation = Field(default_factory=DiagramInsertLocation)


# Each export spawns a headless Chromium; two at a time keeps the workbench
# container's memory bounded when several people export at once.
_office_slots = asyncio.Semaphore(2)


@router.post(
    "/tools/export_canvas_office",
    tags=["diagrams"],
    operation_id="export_canvas_office",
    description=(
        "Render the diagram with maxGraph and return a DOCX or PPTX file. Optionally "
        "append to an existing document supplied by the file adapter. Response is "
        "binary and must be saved/published by the tool bridge as a user-downloadable "
        "attachment. The original file is never overwritten.\n\n"

        "REQUIRED APPROVAL STEP — do this before ever calling this tool: after the "
        "diagram is created/edited with create_canvas_diagram, decide the insertion "
        "point (if the user named one, use it; otherwise read the target document's "
        "existing structure and pick the most sensible spot — e.g. after the section "
        "it illustrates, or at the end if the document has no natural place for it), "
        "then ask the user one combined question that shows the diagram preview, "
        "states the proposed location in plain words, and offers exactly two choices: "
        "'Approve and insert' or 'Edit diagram'. Wait for an explicit reply. Only call "
        "this tool after that explicit approval. If the user asks for changes instead, "
        "apply them (re-calling create_canvas_diagram, or using the user's own edits "
        "made directly in the editor UI) and ask the same combined question again for "
        "the new version — ask once per version, never repeat the question after it is "
        "already approved unless the diagram or location changes again. This approval "
        "gate applies only to inserting into a document; creating/previewing/editing a "
        "standalone diagram never requires it.\n\n"

        "`location.position` controls where the image lands: 'end' (default) appends "
        "a new page (docx) or new last slide (pptx); 'start' inserts before all "
        "existing content; 'after_heading' (docx) inserts right after the first "
        "paragraph whose text contains `location.heading`; 'after_slide' (pptx) "
        "inserts right after the slide matched by `location.slide_index` (0-based, "
        "existing slides only) or `location.slide_title`. An unmatched heading or "
        "slide title is an error — re-check the document structure and either supply "
        "a value that matches or fall back to 'end' rather than guessing."
    ),
)
async def export_canvas_office(
    body: ExportCanvasOfficeBody,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    config.check_auth(x_api_key)
    _user_id, owner = owner_for(request)

    if not body.diagram.elements:
        raise HTTPException(422, "Office export requires at least 1 element.")

    _check_diagram_limits(body.diagram)

    try:
        existing = (
            base64.b64decode(body.existing_document_base64, validate=True)
            if body.existing_document_base64
            else None
        )
        async with _office_slots:
            diagram = await asyncio.to_thread(hydrate_diagram, body.diagram)
            png = await asyncio.wait_for(
                render_diagram_png(diagram, MAXGRAPH_JS_PATH), timeout=60
            )
            credits = "\n".join(
                dict.fromkeys(
                    e.attribution for e in diagram.elements if e.attribution
                )
            )
            document_bytes = await asyncio.to_thread(
                insert_diagram_png,
                png,
                diagram.title,
                body.format,
                existing,
                credits,
                body.location.model_dump(),
            )
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(422, str(exc)) from exc
    except IconifyError as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ImportError, FileNotFoundError) as exc:
        raise HTTPException(
            503, "Office export dependencies or renderer bundle are not installed."
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(504, "Diagram export timed out.") from exc

    types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }

    job_id = uuid4().hex[:12]
    safe_title = re.sub(
        r"[^A-Za-z0-9._-]+", "-", diagram.title or "diagram"
    ).strip("-") or "diagram"
    filename = f"{safe_title}.{body.format}"
    key = document_key(owner.name, job_id, filename)

    s3, _s3_public, bucket = get_default_clients()
    version = upload_bytes(
        s3, bucket, key, document_bytes, types[body.format]
    )
    download_url = links.artifact_url(key)
    size = len(document_bytes)

    return {
        "filename": filename,
        "artifact_key": key,
        "version": version,
        "download_url": download_url,
        "url": download_url,
        "content_type": types[body.format],
        "size_bytes": size,
        "files": [{
            "name": filename,
            "url": download_url,
            "type": types[body.format],
            "size": size,
        }],
        "markdown": f"\U0001f4c4 [{filename}]({download_url})",
        "message": (
            "The diagram was exported and stored as a new file. "
            "The original document was not overwritten."
        ),
    }
