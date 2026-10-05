"""The editor, its thumbnails and its exports must show the same slide.

Covers the causes found for "branding in the editor, missing from the thumbnail" and
"a new slide previews as a dark cover": editor URLs left in stored HTML, thumbnails cached
across theme changes, and new slides built by emptying the current one.
"""
import base64

import pytest

from conftest import BUCKET
from routes import viewer_editor
from routes import viewer_editor_store as store
from test_viewer_editor_cache import CacheFakeS3, DECK_KEY, FOLDER, png_result
from workspace_agent.decks import client as studio_client

EDITOR = "https://chat.example.com/workbench/artifacts/-/edit"


def test_editor_urls_are_returned_to_their_stored_form_whatever_the_prefix():
    html = (f'<div style="mask: url(&quot;{EDITOR}/asset/tok.en_1-x/sami/icons/a.svg&quot;)">'
            f'<img src="{EDITOR}/asset/tok/sami/assets/logo.svg">'
            f'<img src="http://10.0.0.5:8000/artifacts/-/edit/picture/tok/photo.png">'
            '<img src="/ds/sami/assets/other.svg"></div>')
    assert store.clean_editor_urls(html) == (
        '<div style="mask: url(&quot;/ds/sami/icons/a.svg&quot;)">'
        '<img src="/ds/sami/assets/logo.svg"><img src="../images/photo.png">'
        '<img src="/ds/sami/assets/other.svg"></div>')


def seed(fake, slides):
    state = {"v": 1, "title": "T", "design_system": "sami", "filename": "T.pptx", "pictures": [], "slides": slides}
    fake.put(FOLDER + "/" + store.STATE_NAME, store.encode(state))


@pytest.fixture
def fake_s3(monkeypatch):
    fake = CacheFakeS3()
    monkeypatch.setattr(viewer_editor, "credential", lambda token: {"key": DECK_KEY, "o": "u-test"})
    monkeypatch.setattr(viewer_editor, "clients", lambda: (fake, BUCKET))
    viewer_editor._inflight.clear()
    viewer_editor._theme_cache.clear()
    return fake


def test_a_save_never_stores_editor_urls(fake_s3):
    seed(fake_s3, [{"id": "s1", "name": "a", "html": "<div>a</div>", "layout": "", "skip": False}])
    _, rev, _ = store.load(fake_s3, BUCKET, DECK_KEY)
    patch = {"order": ["s1"], "slides": {"s1": {"html": f'<div><img src="{EDITOR}/asset/tok/sami/logo.svg"></div>'}}}
    store.save(fake_s3, BUCKET, DECK_KEY, rev, None, "req-00000010", patch=patch)
    state, _, _ = store.load(fake_s3, BUCKET, DECK_KEY)
    assert state["slides"][0]["html"] == '<div><img src="/ds/sami/logo.svg"></div>'


def test_slides_saved_with_editor_urls_render_with_the_theme_paths(fake_s3, monkeypatch):
    seed(fake_s3, [{"id": "s1", "name": "a", "html": f'<div><img src="{EDITOR}/asset/tok/sami/logo.svg"></div>',
                    "layout": "", "skip": False}])
    sent = []
    monkeypatch.setattr(studio_client, "render", lambda ds, slides, **kw: sent.append(slides) or png_result(b"p"))
    viewer_editor.render_one("tok", "s1")
    assert sent[0][0]["html"] == '<div><img src="/ds/sami/logo.svg"></div>'


def test_a_theme_change_renders_the_thumbnail_again(fake_s3, monkeypatch):
    seed(fake_s3, [{"id": "s1", "name": "a", "html": "<div>a</div>", "layout": "", "skip": False}])
    calls = []
    monkeypatch.setattr(studio_client, "render", lambda *a, **kw: calls.append(1) or png_result(b"p"))
    theme = {"value": "v1"}
    monkeypatch.setattr(viewer_editor, "theme_fingerprint", lambda ds: theme["value"])
    viewer_editor.render_one("tok", "s1")
    viewer_editor.render_one("tok", "s1")
    assert len(calls) == 1, "same theme: served from the cache"
    theme["value"] = "v2"
    viewer_editor.render_one("tok", "s1")
    assert len(calls) == 2, "changed theme: rendered again, never the old picture"


def test_a_slide_added_after_the_cover_starts_from_the_content_layout(fake_s3, index):
    seed(fake_s3, [{"id": "s1", "name": "a", "html": '<div class="slide dark">x</div>', "layout": "01-cover", "skip": False}])
    added = viewer_editor.layout_template("tok", "01-cover")
    assert added["layout"] == "03-content"
    assert added["html"] == '<div class="slide"><h2 class="slidetitle">Content</h2></div>'


def test_a_slide_added_after_a_content_slide_keeps_its_layout(fake_s3, index):
    seed(fake_s3, [{"id": "s1", "name": "a", "html": '<div class="slide">x</div>', "layout": "03-content", "skip": False}])
    assert viewer_editor.layout_template("tok", "03-content")["layout"] == "03-content"


def test_the_theme_fingerprint_follows_the_index(fake_s3, index):
    first = viewer_editor.theme_fingerprint("sami")
    viewer_editor._theme_cache.clear()
    (index / "catalog.json").write_text((index / "catalog.json").read_text().replace("Content", "Content v2"))
    assert viewer_editor.theme_fingerprint("sami") != first
