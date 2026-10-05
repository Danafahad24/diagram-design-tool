"""Manual editing added around the existing viewer, without changing its sources."""
from __future__ import annotations
import base64
import html
import json
import logging
import mimetypes
import os
import re
import hashlib
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import quote, urlsplit, parse_qs, unquote
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, JSONResponse, HTMLResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import run_in_threadpool
from security.cors import cors_headers
from security.session import optional_session_user
from workspace_agent.common import links, minio, ownership, shortlinks, tokens, themes
from workspace_agent.common.identity import workspace_name
from workspace_agent.decks import catalogue, client
from . import viewer_editor_store as store

router = APIRouter(include_in_schema=False)
PREFIX = '/artifacts/-/edit'
ASSETS = Path(__file__).with_name('viewer_editor_assets')
log = logging.getLogger('workbench.viewer_editor')

# How many renders (thumbnail or export) may be in flight against studio at
# once. studio renders with a headless browser, which is the expensive,
# queueing resource here - not this process's own CPU or memory, which is
# why this is a small, dedicated limit rather than anything derived from
# the threadpool size. Configurable because "appropriate for the current
# studio service" depends on how studio itself is deployed, not on this code.
_RENDER_CONCURRENCY = max(1, int(os.environ.get('VIEWER_EDITOR_RENDER_CONCURRENCY', '2')))
_render_semaphore = threading.Semaphore(_RENDER_CONCURRENCY)

# Singleflight: concurrent requests for the exact same cache key (same slide
# content, or same deck revision+kind for an export) share one studio call
# instead of each starting their own. Keyed by the cache key itself, which
# is already a content hash - never a token, never raw HTML.
_inflight_lock = threading.Lock()
_inflight: dict[str, threading.Event] = {}


def _rendered(label, s3, bucket, object_key, max_bytes, content_type, build, *, t_load, cache_key):
    """Serve `object_key` from the persistent cache, or render it once (with
    bounded concurrency and in-flight de-duplication, shared across every
    render kind) and store it before returning. Logs how long each stage
    took - loading the source (`t_load`, measured by the caller before this
    function even starts), the cache lookup, waiting for a render slot, the
    render itself, and storing the result - identified only by `label` and
    the cache key's own hash, never a token or any slide/deck content.

    `build()` takes no arguments, returns raw bytes, and runs under the
    bounded semaphore; concurrent callers for the same `object_key` share
    one call to it via the in-flight map below instead of each starting
    their own against studio.
    """
    t_start = time.monotonic()
    cached = store.read_small(s3, bucket, object_key, max_bytes)
    t_cache = time.monotonic() - t_start
    if cached is not None:
        log.info('%s timing: load=%.3fs cache=%.3fs hit=true total=%.3fs key=%s',
                 label, t_load, t_cache, t_load + t_cache, cache_key[:12])
        return cached

    with _inflight_lock:
        event = _inflight.get(object_key)
        leader = event is None
        if leader:
            event = threading.Event()
            _inflight[object_key] = event

    if not leader:
        t_wait_start = time.monotonic()
        # The leader stores the result before setting the event, so once this
        # wait returns, re-reading the cache below either finds it or the
        # leader's render genuinely failed - never a third render of the same key.
        finished = event.wait(timeout=180)
        t_wait = time.monotonic() - t_wait_start
        if not finished:
            raise HTTPException(503, 'The slide renderer is busy. Try again shortly.')
        cached = store.read_small(s3, bucket, object_key, max_bytes)
        if cached is not None:
            log.info('%s timing: load=%.3fs cache=%.3fs wait=%.3fs hit=true (followed another request\'s render) key=%s',
                     label, t_load, t_cache, t_wait, cache_key[:12])
            return cached
        raise HTTPException(502, 'The slide could not be rendered. Try again.')

    try:
        t_sem_start = time.monotonic()
        with _render_semaphore:
            t_wait = time.monotonic() - t_sem_start
            t_render_start = time.monotonic()
            raw = build()
            t_render = time.monotonic() - t_render_start
        t_store_start = time.monotonic()
        store.store_small(s3, bucket, object_key, raw, content_type)
        t_store = time.monotonic() - t_store_start
        log.info('%s timing: load=%.3fs cache=%.3fs wait=%.3fs render=%.3fs store=%.3fs total=%.3fs hit=false key=%s',
                 label, t_load, t_cache, t_wait, t_render, t_store,
                 t_load + t_cache + t_wait + t_render + t_store, cache_key[:12])
        return raw
    finally:
        with _inflight_lock:
            _inflight.pop(object_key, None)
        event.set()


_theme_lock = threading.Lock()
_theme_cache: dict[str, tuple[float, str]] = {}


def theme_fingerprint(design_system):
    """A hash of what a render depends on besides the slide: the design system's index
    (layouts, their stylesheets, the overlay's patches) and the stylesheet files it links
    (by size and modification time). Part of every thumbnail and export cache key, so a
    theme or overlay change is never answered with a picture of the old theme. Kept for a
    minute so a rail of thumbnails does not stat the theme once per slide."""
    now = time.monotonic()
    with _theme_lock:
        hit = _theme_cache.get(design_system)
        if hit and now - hit[0] < 60:
            return hit[1]
    h = hashlib.sha256()
    try:
        catalog = catalogue.read_catalog(design_system)
        h.update(json.dumps(catalog, sort_keys=True, default=str).encode())
        sheets = set(catalog.get('globalCss') or [])
        for layout in catalog.get('layouts') or []:
            sheets.update(layout.get('stylesheets') or [])
        root = themes.design_systems_dir().resolve()
        for url in sorted(sheets):
            m = re.match(r'/ds/([a-z0-9.-]+)/(.+)$', str(url))
            if not m:
                continue
            file = (root / m[1] / m[2]).resolve()
            if file.is_relative_to(root) and file.is_file():
                st = file.stat()
                h.update(f'{url}:{st.st_size}:{st.st_mtime_ns}'.encode())
    except Exception:
        log.warning('theme fingerprint unavailable for %s', design_system, exc_info=True)
        h.update(b'unavailable')
    value = h.hexdigest()
    with _theme_lock:
        _theme_cache[design_system] = (now, value)
    return value


def credential(token):
    try:
        p = tokens.verify_artifact_token(token, tokens.default_secret(), ownership.normalize_key,
                                         kind=tokens.EDIT, key_owner=ownership.key_owner)
        if p['ver'] != 'viewer-editor-v1' or not p['key'].endswith('/' + ownership.DECK_MANIFEST):
            raise tokens.TokenError('Wrong editor')
        return p
    except Exception as exc:
        raise HTTPException(403, 'Editing access expired. Open a new preview from your own chat.') from exc


async def access(token, request):
    p = credential(token)
    session = await optional_session_user(request)
    if session is not None and workspace_name(session.id) != p['o']:
        raise HTTPException(404, 'Presentation not found.')
    return p


def clients():
    s3, _, bucket = minio.get_default_clients()
    return s3, bucket


def load(token):
    p = credential(token)
    s3, bucket = clients()
    state, revision, etag = store.load(s3, bucket, p['key'])
    return p, state, revision


def public(path):
    return links.public_base() + path


@router.options(PREFIX + '/{path:path}')
def preflight(path: str, request: Request):
    return Response(headers={**cors_headers(request.headers.get('origin', '')), 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                             'Access-Control-Allow-Headers': 'Content-Type, If-Match', 'Access-Control-Max-Age': '600'})


@router.get(PREFIX + '/static/{name}')
def static(name: str):
    if name not in {'editor.js', 'child.js', 'editor.css', 'child.css', 'dependencies.js', 'dependencies.js.LEGAL.txt'}:
        raise HTTPException(404)
    return FileResponse(ASSETS / name, headers={'Access-Control-Allow-Origin': '*', 'Cache-Control': 'no-cache'})


@router.get(PREFIX + '/state/{token}')
async def state(token: str, request: Request):
    await access(token, request)
    _, value, revision = await run_in_threadpool(load, token)
    return JSONResponse({'state': value, 'revision': revision}, headers={**cors_headers(request.headers.get('origin', '')), 'Cache-Control': 'no-store'})


@router.post(PREFIX + '/save/{token}')
async def save(token: str, request: Request):
    p = await access(token, request)
    raw = await limited_body(request)
    try:
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise store.EditorError('A save request must be an object.')
        revision = request.headers.get('if-match', '').strip('"')
        if not revision:
            raise HTTPException(428, 'A presentation revision is required.')
        s3, bucket = clients()
        t_start = time.monotonic()
        # `patch` carries only the dirty slides plus the slide order; `state`
        # (the whole deck) is still accepted for older editor scripts.
        value, revision = await run_in_threadpool(store.save, s3, bucket, p['key'], revision, body.get('state'), body.get('request_id'),
                                                  patch=body.get('patch'))
        patch = body.get('patch') if isinstance(body.get('patch'), dict) else None
        log.info('save timing: total=%.3fs bytes=%d slides=%d changed=%s',
                 time.monotonic() - t_start, len(raw), len(value['slides']),
                 len(patch.get('slides') or {}) if patch else 'all')
        return JSONResponse({'revision': revision}, headers={**cors_headers(request.headers.get('origin', '')), 'Cache-Control': 'no-store'})
    except store.Conflict as exc:
        return JSONResponse({'detail': str(exc)}, status_code=412, headers=cors_headers(request.headers.get('origin', '')))
    except (store.EditorError, ValueError, TypeError) as exc:
        return JSONResponse({'detail': str(exc)}, status_code=400, headers=cors_headers(request.headers.get('origin', '')))


async def limited_body(request, limit=store.MAX_BYTES):
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, 'Upload exceeds the size limit.')
        chunks.append(chunk)
    return b''.join(chunks)


@router.post(PREFIX + '/image/{token}')
async def image(token: str, request: Request):
    await access(token, request)
    raw = await limited_body(request, store.MAX_IMAGE_BYTES)
    try:
        result = await run_in_threadpool(store.image_data, raw)
        return JSONResponse(result, headers=cors_headers(request.headers.get('origin', '')))
    except store.EditorError as exc:
        return JSONResponse({'detail': str(exc)}, status_code=400, headers=cors_headers(request.headers.get('origin', '')))


def pictures(state):
    return {p['name']: base64.b64decode(p['data']) for p in state.get('pictures') or []}


def select_revision(token, revision):
    p, state, current = load(token)
    if current != revision:
        raise HTTPException(412, 'The presentation changed. Refresh before exporting.')
    return state


def render_one(token, sid):
    """A thumbnail for slide `sid` as the presentation stands right now.

    Deliberately does not require the caller's `revision` to match the
    deck's current one: that would fail this slide's own, unrelated-to-it
    thumbnail every time any OTHER slide is saved first, which is exactly
    the unnecessary invalidation this fix removes. Freshness here is scoped
    to the one slide, via `thumbnail_cache_key`, not to the whole deck.
    """
    t_start = time.monotonic()
    p, source, _revision = load(token)
    slide = next((s for s in source['slides'] if s['id'] == sid), None)
    if not slide:
        raise HTTPException(404, 'Slide not found.')
    slide = store.render_slides([slide])[0]
    pics = pictures(source)
    cache_key = store.thumbnail_cache_key(source['design_system'], slide, pics, theme_fingerprint(source['design_system']))
    object_key = store.thumbnail_object_key(p['key'], cache_key)
    t_load = time.monotonic() - t_start

    def build():
        result = client.render(source['design_system'], [slide], pictures=pics, pdf=False, png=True)
        return base64.b64decode(result['slides'][0]['png'])

    return _rendered('thumbnail', *clients(), object_key, store.MAX_THUMB_BYTES, 'image/png', build,
                      t_load=t_load, cache_key=cache_key)


@router.get(PREFIX + '/thumbnail/{token}/{sid}')
async def thumbnail(token: str, sid: str, request: Request, revision: str = ''):
    # `revision` is accepted and ignored for cache correctness (kept so the
    # existing query string still works as a browser cache-buster); see
    # render_one's docstring for why per-slide freshness must not depend on it.
    await access(token, request)
    raw = await run_in_threadpool(render_one, token, sid)
    return Response(raw, media_type='image/png', headers={**cors_headers(request.headers.get('origin', '')), 'Cache-Control': 'private, max-age=3600'})


def export_file(token, revision, kind):
    """The deck exported as `kind`, for exactly the given (already-saved)
    revision. Unlike thumbnails, this intentionally keeps the strict
    revision match in `select_revision`: an export's rendering inputs are
    every slide at once, so there is no finer-grained "unaffected part" to
    reuse across revisions the way a single slide's thumbnail has."""
    t_start = time.monotonic()
    if kind not in ('pptx', 'pdf'):
        raise HTTPException(404)
    deck_key = credential(token)['key']  # no I/O: the key travels in the signed token itself
    source = select_revision(token, revision)
    source = dict(source, slides=store.render_slides(source['slides']))
    object_key = store.export_object_key(deck_key, revision, kind, theme_fingerprint(source['design_system']))
    t_load = time.monotonic() - t_start

    if kind == 'pptx':
        def build():
            result = client.export(source['design_system'], source['slides'], pictures=pictures(source), title=source['title'])
            return store.apply_skip(base64.b64decode(result['pptx']), source['slides'])
        mime = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    else:
        def build():
            # Explicitly include skipped slides: a printable record of the whole deck.
            result = client.render(source['design_system'], source['slides'], pictures=pictures(source), png=False, pdf=True)
            return base64.b64decode(result['pdf'])
        mime = 'application/pdf'

    raw = _rendered('export', *clients(), object_key, store.MAX_EXPORT_BYTES, mime, build,
                     t_load=t_load, cache_key=object_key)
    return raw, mime


@router.get(PREFIX + '/export/{token}/{kind}')
async def export(token: str, kind: str, request: Request, revision: str):
    await access(token, request)
    raw, mime = await run_in_threadpool(export_file, token, revision, kind)
    return Response(raw, media_type=mime, headers={**cors_headers(request.headers.get('origin', '')), 'Cache-Control': 'no-store',
                    'Content-Disposition': f'attachment; filename="Presentation.{kind}"'})


def catalog_for(source):
    return catalogue.read_catalog(source['design_system'])


def around(catalog, slide):
    layouts = catalog.get('layouts') or []
    selected = next((x for x in layouts if slide.get('layout') in {x.get('id'), x.get('path')}), None)
    if selected and 'stylesheets' in selected:
        out = selected
    else:
        out = dict(layouts[0] if layouts else {})
        out['lang'] = out['dir'] = ''   # studio's harness gives a layout-less slide neither
        out['stylesheets'] = list(dict.fromkeys((catalog.get('globalCss') or []) + [v for x in layouts for v in x.get('stylesheets') or []]))
    if out.get('host') or out.get('scripts'):
        raise store.EditorError('This design system requires scripted components and is not supported by the manual editor yet.')
    return out


def _rewriter(token, source):
    asset_base = public(PREFIX + '/asset/' + token)
    picture_base = public(PREFIX + '/picture/' + token + '/')
    names = [n for n in pictures(source)]
    def rewrite(text):
        text = re.sub(r'/ds/([a-z0-9.-]+)/', lambda m: asset_base + '/' + m[1] + '/', text)
        # Pictures are referenced by URL, not inlined as base64: inlining made
        # every serialized slide (and so every save, undo step and postMessage)
        # carry the full image bytes. The editor maps this URL back to
        # `../images/<name>` before saving, so stored HTML keeps its original form.
        for name in names:
            text = text.replace('../images/' + name, picture_base + name)
        return text
    return rewrite


def _page(token, source, catalog, surrounding, sid, body):
    nonce = secrets.token_urlsafe(24)
    rewrite = _rewriter(token, source)
    css = ''.join('<link rel="stylesheet" href="' + html.escape(rewrite(x), quote=True) + '">' for x in surrounding.get('stylesheets') or [])
    css += ''.join('<style>' + rewrite(x).replace('</style', '<\\/style') + '</style>' for x in surrounding.get('inlineStyles') or [])
    # Editor-only runtime changes are never serialized back to a theme stylesheet.
    # The same <html lang dir> studio's harness gives this layout: an RTL or Arabic layout
    # styled through [dir]/:lang() must look in the editor as it does in every render.
    lang, direction = surrounding.get('lang') or '', surrounding.get('dir') or ''
    page = ('<!doctype html><html' + (' lang="' + html.escape(lang, quote=True) + '"' if lang else '')
            + (' dir="' + html.escape(direction, quote=True) + '"' if direction else '') + '><head><meta charset="utf-8">' + css)
    page += '<link rel="stylesheet" href="' + public(PREFIX + '/static/child.css') + '"></head><body>' + rewrite(body)
    patches = [p for p in catalog.get('patches', []) if p.get('in_slides') and p.get('html')]
    settings = json.dumps({'sid': sid, 'patches': patches}).replace('<', '\\u003c')
    page += '<script nonce="' + nonce + '">window.VE_CONFIG=' + settings + ';</script>'
    page += '<script nonce="' + nonce + '" src="' + public(PREFIX + '/static/dependencies.js') + '"></script>'
    page += '<script nonce="' + nonce + '" src="' + public(PREFIX + '/static/child.js') + '"></script></body></html>'
    base = links.public_base()
    policy = f"default-src 'none'; script-src 'nonce-{nonce}'; style-src {base} 'unsafe-inline'; img-src {base} data: blob:; font-src {base} data:; connect-src 'none'; base-uri 'none'; form-action 'none'; sandbox allow-scripts"
    return page, policy


def frame_html(token, sid):
    """One saved slide rendered into the page (kept for older editor scripts)."""
    _, source, _ = load(token)
    slide = next((s for s in source['slides'] if s['id'] == sid), None)
    if not slide:
        raise HTTPException(404, 'Slide not found.')
    catalog = catalog_for(source)
    return _page(token, source, catalog, around(catalog, slide), sid, store.safe_html(slide['html']))


def shell_html(token, layout):
    """A reusable editing frame for every slide of one layout: the layout's
    stylesheets and the editor scripts, with no slide in it. The editor loads
    slides into it from its own live state with a postMessage, so switching
    slides, or opening a slide that has not been saved yet, needs neither a
    new frame nor a save first. The design-system CSS is the only thing that
    differs between layouts, which is why frames are shared per layout."""
    t_start = time.monotonic()
    _, source, _ = load(token)
    catalog = catalog_for(source)
    result = _page(token, source, catalog, around(catalog, {'layout': layout}), None, '')
    log.info('shell timing: total=%.3fs', time.monotonic() - t_start)
    return result


@router.get(PREFIX + '/frame/{token}/{sid}')
async def frame(token: str, sid: str, request: Request):
    await access(token, request)
    try:
        page, policy = await run_in_threadpool(frame_html, token, sid)
    except store.EditorError as exc:
        return HTMLResponse('<p>' + html.escape(str(exc)) + '</p>', status_code=422)
    return HTMLResponse(page, headers={'Content-Security-Policy': policy, 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})


@router.get(PREFIX + '/shell/{token}')
async def shell(token: str, request: Request, layout: str = ''):
    await access(token, request)
    try:
        page, policy = await run_in_threadpool(shell_html, token, layout[:200])
    except store.EditorError as exc:
        return HTMLResponse('<p>' + html.escape(str(exc)) + '</p>', status_code=422)
    return HTMLResponse(page, headers={'Content-Security-Policy': policy, 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})


COVER_LIKE = re.compile(r'cover|title|closing|end|section|divider|agenda', re.I)


def layout_template(token, layout):
    """The design system's own fragment for a new slide, with its branding (logo,
    classification bar, footer) intact. A slide added after a cover gets the first content
    layout instead of a copy of the cover."""
    _, source, _ = load(token)
    design = source['design_system']
    layouts = catalog_for(source).get('layouts') or []
    ids = [l.get('id') for l in layouts]
    current = next((l for l in layouts if layout in {l.get('id'), l.get('path')}), None)
    chosen = current
    if current is None or COVER_LIKE.search(str(current.get('id') or '') + ' ' + str(current.get('name') or '')):
        chosen = next((l for l in layouts if not COVER_LIKE.search(str(l.get('id') or '') + ' ' + str(l.get('name') or ''))), current)
    if chosen is None:
        raise HTTPException(404, 'No layout to start a slide from.')
    found = catalogue.fragments(design, [chosen['id']]).get('fragments', {}).get(chosen['id'])
    if not found:
        raise HTTPException(404, 'No layout to start a slide from.')
    return {'layout': chosen['id'] if chosen['id'] in ids else layout, 'html': store.safe_html(found)}


@router.get(PREFIX + '/layout/{token}')
async def layout(token: str, request: Request, layout: str = ''):
    await access(token, request)
    try:
        result = await run_in_threadpool(layout_template, token, layout[:200])
    except store.EditorError as exc:
        return JSONResponse({'detail': str(exc)}, status_code=422, headers=cors_headers(request.headers.get('origin', '')))
    return JSONResponse(result, headers={**cors_headers(request.headers.get('origin', '')), 'Cache-Control': 'private, max-age=300'})


def picture_bytes(token, name):
    _, source, _ = load(token)
    raw = pictures(source).get(name)
    if raw is None:
        raise HTTPException(404)
    return raw


@router.get(PREFIX + '/picture/{token}/{name:path}')
async def picture(token: str, name: str, request: Request):
    await access(token, request)
    raw = await run_in_threadpool(picture_bytes, token, name)
    mime = mimetypes.guess_type(name)[0] or 'image/png'
    if not mime.startswith('image/'):
        raise HTTPException(404)
    # Sandboxed so that a picture opened directly (an SVG in particular) can never run as a page on this origin.
    return Response(raw, media_type=mime, headers={'Access-Control-Allow-Origin': '*', 'Cache-Control': 'private, max-age=3600',
                                                   'X-Content-Type-Options': 'nosniff',
                                                   'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; sandbox"})


@router.get(PREFIX + '/asset/{token}/{design}/{path:path}')
async def asset(token: str, design: str, path: str, request: Request):
    await access(token, request)
    _, source, _ = await run_in_threadpool(load, token)
    if design not in {source['design_system'], source['design_system'] + '.overlay'}:
        raise HTTPException(404)
    root = (themes.design_systems_dir() / design).resolve()
    file = (root / path).resolve()
    if not file.is_relative_to(root) or file.suffix.lower() not in {'.css', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2', '.otf', '.ttf'} or not file.is_file():
        raise HTTPException(404)
    if file.suffix.lower() == '.css':
        text = file.read_text()
        text = re.sub(r'/ds/([a-z0-9.-]+)/', lambda m: public(PREFIX + '/asset/' + token + '/' + m[1] + '/'), text)
        return Response(text, media_type='text/css', headers={'Access-Control-Allow-Origin': '*', 'Cache-Control': 'private, max-age=3600'})
    return FileResponse(file, headers={'Access-Control-Allow-Origin': '*', 'Cache-Control': 'private, max-age=3600', 'X-Content-Type-Options': 'nosniff'})


class EditorMiddleware(BaseHTTPMiddleware):
    """Enrich only an owner's freshly generated preview; never promote a read token."""
    async def dispatch(self, request, call_next):
        path = request.url.path
        token = request.query_params.get('editor', '')
        generate = path == '/tools/preview_deck' and request.method == 'POST'
        enrich = path.startswith('/artifacts/') and token and request.method == 'GET' and not path.startswith(PREFIX)
        response = await call_next(request)
        if not (generate or enrich) or response.status_code != 200:
            return response
        raw = b''.join([chunk async for chunk in response.body_iterator])
        headers = dict(response.headers)
        try:
            if generate:
                import config
                from security.identity import owner_for, presented_key
                config.check_auth(presented_key(request.headers))
                _, owner = owner_for(request)
                result = json.loads(raw)
                iframe = result.get('preview_iframe_html', '')
                url = result.get('url', '')
                parts = urlsplit(url)
                s3, bucket = clients()
                if parts.path.startswith('/artifacts/-/v/'):
                    record = await run_in_threadpool(shortlinks.resolve, s3, bucket, parts.path.rsplit('/', 1)[-1])
                    key = record['key']
                else:
                    key = unquote(parts.path.removeprefix('/artifacts/'))
                if ownership.key_owner(key) != owner.name or not key.endswith('/' + ownership.DECK_MANIFEST):
                    raise ValueError('Not an owned generated deck')
                await run_in_threadpool(store.load, s3, bucket, key)
                edit = tokens.sign_artifact_token(key, 'deck.json', tokens.default_secret(), ownership.normalize_key,
                       owner=owner.name, kind=tokens.EDIT, version='viewer-editor-v1')
                result['preview_iframe_html'] = re.sub(r'(src="[^"]+)(")', lambda m: m[1] + ('&amp;' if '?' in m[1] else '?') + 'editor=' + edit + m[2], iframe, count=1)
                raw = json.dumps(result, ensure_ascii=False).encode()
            else:
                p = await access(token, request)
                parts = request.url.path
                s3, bucket = clients()
                if parts.startswith('/artifacts/-/v/'):
                    record = await run_in_threadpool(shortlinks.resolve, s3, bucket, parts.rsplit('/', 1)[-1])
                    key = record['key']
                else:
                    key = unquote(parts.removeprefix('/artifacts/'))
                if key != p['key']:
                    raise ValueError('Mismatched viewer')
                text = raw.decode()
                if '<div id="deck"' in text:
                    script = '<link rel="stylesheet" href="' + public(PREFIX + '/static/editor.css') + '">' + '<script src="' + public(PREFIX + '/static/dependencies.js') + '"></script><script src="' + public(PREFIX + '/static/editor.js') + '" data-token="' + html.escape(token, quote=True) + '"></script>'
                    raw = text.replace('</body>', script + '</body>').encode()
                    headers['Referrer-Policy'] = 'no-referrer'
        except Exception:
            # The existing read-only preview still opens when editing cannot be enabled.
            log.exception('Manual editor could not be attached; original preview retained')
        headers['content-length'] = str(len(raw))
        return Response(raw, status_code=response.status_code, headers=headers)


def install(app):
    app.include_router(router)
    app.add_middleware(EditorMiddleware)
