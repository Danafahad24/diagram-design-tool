"""Source-backed manual deck edits. Original preview sources remain untouched.

All writes use S3 conditional requests; a process-local lock is not sufficient.
The original source is immutable and read-only here. Editor revisions have their own
object, and exports always use a requested, verified revision of that object.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import re
import uuid
import zipfile
from pathlib import Path
from urllib.parse import unquote
from lxml import etree, html
from PIL import Image

MAX_BYTES = 24 * 1024 * 1024
MAX_SLIDES = 80
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
MAX_THUMB_BYTES = 4 * 1024 * 1024
MAX_EXPORT_BYTES = 64 * 1024 * 1024
STATE_NAME = 'editor-state.json'
PARSER = html.HTMLParser(remove_comments=False, no_network=True)
PICTURE_REF = re.compile(r'\.\./images/([^"\'\s)]+)')
# Addresses the browser editor uses for theme assets and pictures, whatever origin or
# path prefix the deployment serves it under. They must never reach stored HTML: the
# renderer (thumbnails, PDF, PPTX) loads nothing from outside its own origin, so a logo
# left as an editor URL shows in the editor and silently vanishes from every render.
EDITOR_ASSET_URL = re.compile(r'[^\s"\'();&]*?/artifacts/-/edit/asset/[^/\s"\'();&]+/')
EDITOR_PICTURE_URL = re.compile(r'[^\s"\'();&]*?/artifacts/-/edit/picture/[^/\s"\'();&]+/')

def clean_editor_urls(text):
    """Stored form of slide HTML: editor asset URLs back to `/ds/`, editor picture URLs
    back to `../images/`. Also repairs slides saved before the editor did this itself."""
    if not isinstance(text, str):
        return text
    return EDITOR_PICTURE_URL.sub('../images/', EDITOR_ASSET_URL.sub('/ds/', text))


def render_slides(slides):
    """Slides as the renderer must see them (see `clean_editor_urls`)."""
    return [dict(s, html=clean_editor_urls(s['html'])) for s in slides]


class EditorError(ValueError):
    pass

class Conflict(EditorError):
    pass


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_html(source):
    if not isinstance(source, str) or len(source.encode()) > 16 * 1024 * 1024:
        raise EditorError('A slide exceeds the 16 MB HTML limit, including images.')
    try:
        root = html.fragment_fromstring(source, create_parent='div', parser=PARSER)
    except (etree.ParserError, etree.XMLSyntaxError) as exc:
        raise EditorError('This slide contains invalid HTML.') from exc
    if len(root) != 1 or (root.text or '').strip():
        raise EditorError('Each slide must have one root element.')
    banned = {'script', 'iframe', 'object', 'embed', 'frame', 'frameset', 'base', 'meta', 'link', 'style', 'form', 'input', 'button', 'textarea', 'select', 'foreignobject', 'animate', 'set'}
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        tag = el.tag.split('}')[-1].lower()
        if tag in banned:
            raise EditorError('Slides cannot contain scripts, forms, embedded pages, or document-level elements.')
        for name, value in el.attrib.items():
            name = name.lower().split('}')[-1]
            if name.startswith('on') or name in {'srcdoc', 'nonce', 'formaction'}:
                raise EditorError('Executable attributes are not allowed in slides.')
            if name in {'href', 'src', 'action', 'data', 'poster', 'background'}:
                clean = ''.join(value.split()).lower()
                if clean.startswith(('javascript:', 'vbscript:')) or (clean.startswith('data:') and not clean.startswith(('data:image/png;base64,', 'data:image/jpeg;base64,', 'data:image/svg+xml'))):
                    raise EditorError('Unsupported slide URL.')
            if name == 'style' and re.search(r'expression\s*\(|javascript\s*:|-moz-binding', value, re.I):
                raise EditorError('Unsupported style expression.')
    # Validate without rewriting SVG attribute casing or authored HTML formatting.
    return source


def normalize(source, key):
    slides = []
    for i, s in enumerate(source.get('slides') or []):
        item = dict(s)
        item['id'] = uuid.uuid5(uuid.NAMESPACE_URL, key + ':' + str(i) + ':' + s.get('name', '')).hex
        item['html'] = safe_html(s['html'])
        item['skip'] = False
        slides.append(item)
    if not slides or source.get('export') != 'pptx':
        raise EditorError('Manual editing requires a generated presentation with stored HTML source.')
    return {'v': 1, 'title': source.get('title') or 'Presentation', 'design_system': source['design_system'],
            'filename': source.get('filename') or 'Presentation.pptx', 'pictures': source.get('pictures') or [], 'slides': slides}


def checked_state(proposed, original, trusted=()):
    """`trusted` holds slides taken verbatim from `original` (by object
    identity): they were validated when they were stored, so a patch save
    re-validates only the slides it actually changed."""
    if not isinstance(proposed, dict):
        raise EditorError('Invalid presentation state.')
    trusted = {id(s) for s in trusted}
    slides = proposed.get('slides')
    if not isinstance(slides, list) or not 1 <= len(slides) <= MAX_SLIDES:
        raise EditorError('A presentation must contain 1 to 80 slides.')
    out = {k: original[k] for k in ('v', 'title', 'design_system', 'filename', 'pictures')}
    out['slides'] = []
    seen = set()
    for s in slides:
        if not isinstance(s, dict):
            raise EditorError('Each slide must be an object.')
        sid = s.get('id', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', sid) or sid in seen:
            raise EditorError('Slide identifiers must be unique.')
        seen.add(sid)
        out['slides'].append({'id': sid, 'name': str(s.get('name') or sid)[:160],
                              'html': s.get('html') if id(s) in trusted else safe_html(clean_editor_urls(s.get('html'))),
                              'layout': str(s.get('layout') or '')[:200], 'skip': bool(s.get('skip'))})
    if len(encode(out)) > MAX_BYTES:
        raise EditorError('This presentation exceeds the 24 MB editing limit.')
    return out


def read_object(s3, bucket, key):
    response = s3.get_object(Bucket=bucket, Key=key)
    stream = response['Body']
    try:
        raw = stream.read(MAX_BYTES + 1)
    finally:
        stream.close()
    if len(raw) > MAX_BYTES:
        raise EditorError('This presentation exceeds the 24 MB editing limit.')
    return raw, response.get('ETag')


def is_missing(exc):
    return getattr(exc, 'response', {}).get('Error', {}).get('Code') in {'NoSuchKey', '404', 'NotFound'}


def load(s3, bucket, key):
    folder = key.rsplit('/', 1)[0]
    try:
        raw, etag = read_object(s3, bucket, folder + '/' + STATE_NAME)
        state = json.loads(raw)
        return state, digest(raw), etag
    except Exception as exc:
        if not is_missing(exc):
            raise
    raw, _ = read_object(s3, bucket, folder + '/source.json')
    return normalize(json.loads(raw), key), 'initial-' + digest(raw), None


def merge_patch(current, patch):
    """The full proposed deck from a patch: `order` lists every slide id in
    deck order, `slides` maps the ids of new or changed slides to their full
    content. Every other id must already be stored and is reused as is."""
    if not isinstance(patch, dict):
        raise EditorError('Invalid presentation change.')
    order, changed = patch.get('order'), patch.get('slides', {})
    if not isinstance(order, list) or not isinstance(changed, dict):
        raise EditorError('Invalid presentation change.')
    stored = {s['id']: s for s in current['slides']}
    slides, trusted = [], []
    for sid in order:
        if not isinstance(sid, str):
            raise EditorError('Slide identifiers must be unique.')
        if sid in changed:
            item = changed[sid]
            if not isinstance(item, dict):
                raise EditorError('Each slide must be an object.')
            slides.append(dict(item, id=sid))
        elif sid in stored:
            slides.append(stored[sid])
            trusted.append(stored[sid])
        else:
            raise Conflict('This presentation changed in another window. Your local edits remain in this window. Download a recovery copy before reloading.')
    return {'slides': slides}, trusted


def save(s3, bucket, key, revision, proposed, request_id, patch=None):
    current, version, etag = load(s3, bucket, key)
    if current.get('request_id') == request_id and request_id:
        return current, version
    if revision != version:
        raise Conflict('This presentation changed in another window. Your local edits remain in this window. Download a recovery copy before reloading.')
    trusted = ()
    if patch is not None:
        proposed, trusted = merge_patch(current, patch)
    checked = checked_state(proposed, current, trusted)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}', request_id or ''):
        raise EditorError('A save request needs a unique request identifier.')
    checked['request_id'] = request_id
    raw = encode(checked)
    params = {'Bucket': bucket, 'Key': key.rsplit('/', 1)[0] + '/' + STATE_NAME, 'Body': raw,
              'ContentType': 'application/json', 'Tagging': 'retention=deck'}
    params.update({'IfMatch': etag} if etag else {'IfNoneMatch': '*'})
    try:
        s3.put_object(**params)
    except Exception as exc:
        if getattr(exc, 'response', {}).get('Error', {}).get('Code') in {'PreconditionFailed', 'ConditionalRequestConflict', '412', '409'}:
            raise Conflict('This presentation changed in another window. Your local edits have not been discarded.') from exc
        raise
    return checked, digest(raw)


def image_data(raw):
    if len(raw) > MAX_IMAGE_BYTES:
        raise EditorError('Images must be 10 MB or smaller.')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            fmt = im.format
            if fmt not in {'PNG', 'JPEG'}:
                raise EditorError('Upload a PNG or JPEG image.')
            if im.width > 8000 or im.height > 8000 or im.width * im.height > MAX_IMAGE_PIXELS:
                raise EditorError('Images must be at most 8000 pixels per side and 24 megapixels in total.')
            size = [im.width, im.height]
            im.verify()
    except EditorError:
        raise
    except Exception as exc:
        raise EditorError('This image is damaged or unsupported.') from exc
    mime = 'image/png' if fmt == 'PNG' else 'image/jpeg'
    return {'src': f'data:{mime};base64,' + base64.b64encode(raw).decode(), 'size': size}


def thumbnail_cache_key(design_system, slide, pictures, theme=''):
    """A hash of exactly what rendering a thumbnail of this slide depends on:
    the design system, the slide's own HTML and layout, and the bytes of any
    picture its HTML actually references (by name, since a name can be
    reused for different bytes across edits). Nothing about OTHER slides,
    their order, or the deck's overall revision enters this hash, so editing
    or reordering slide B never changes slide A's cache key.

    Slide position/number is deliberately excluded: a thumbnail is always
    rendered as a single-slide deck (`client.render(..., [slide], ...)`), so
    the renderer never sees where the slide sits in the full presentation
    and cannot draw a position-dependent page number into it.

    `theme` is the design system's fingerprint (`theme_fingerprint`): without it a
    thumbnail cached before the theme, its overlay or its patches changed was served
    unchanged for ever, because the slide's own HTML had not changed.
    """
    parts = [design_system, slide.get('layout') or '', slide['html']] + ([theme] if theme else [])
    for name in sorted(set(PICTURE_REF.findall(slide['html']))):
        data = pictures.get(name)
        parts.append(name + ':' + (digest(data) if data is not None else 'missing'))
    return hashlib.sha256('\x1e'.join(parts).encode('utf-8')).hexdigest()


def thumbnail_object_key(deck_key, cache_key):
    """Scoped under the presentation's own (owner-prefixed) folder, so one
    deck's cached thumbnails can never be served for another."""
    return deck_key.rsplit('/', 1)[0] + '/thumbs/' + cache_key + '.png'


def export_object_key(deck_key, revision, kind, theme=''):
    return deck_key.rsplit('/', 1)[0] + '/exports/' + revision + ('-' + theme[:16] if theme else '') + '.' + kind


def read_small(s3, bucket, key, limit):
    """A cached render's bytes, or None if nothing is cached yet. Any other
    storage error is raised - a transient failure must not look like a
    cache miss and trigger a render that then also fails to store. Reads
    its own bound rather than `read_object`'s 24 MB editor-state limit: a
    cached export can legitimately exceed that, and silently truncating one
    would serve a corrupt download instead of just re-rendering it."""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        if is_missing(exc):
            return None
        raise
    stream = response['Body']
    try:
        raw = stream.read(limit + 1)
    finally:
        stream.close()
    return raw if len(raw) <= limit else None


def store_small(s3, bucket, key, raw, content_type):
    s3.put_object(Bucket=bucket, Key=key, Body=raw, ContentType=content_type, Tagging='retention=deck')


def apply_skip(pptx, slides):
    """Keep skipped slides in the file, using the native slideshow flag."""
    dest = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(pptx)) as src, zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            raw = src.read(item)
            m = re.fullmatch(r'ppt/slides/slide(\d+)\.xml', item.filename)
            if m and int(m[1]) <= len(slides):
                root = etree.fromstring(raw)
                if slides[int(m[1]) - 1].get('skip'):
                    root.set('show', '0')
                else:
                    root.attrib.pop('show', None)
                raw = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            out.writestr(item, raw)
    return dest.getvalue()
