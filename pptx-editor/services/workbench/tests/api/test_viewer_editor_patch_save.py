"""Patch saves: the editor sends only the slides it changed plus the slide order.

Exercises `viewer_editor_store.save(..., patch=...)` directly over a fake S3,
the same way test_viewer_editor_cache.py exercises the render paths.
"""
import json

import pytest

from routes import viewer_editor_store as store
from test_viewer_editor_cache import BUCKET, CacheFakeS3, DECK_KEY, FOLDER


def slide(sid, text, layout="l1"):
    return {"id": sid, "name": sid + ".html", "html": f"<div>{text}</div>", "layout": layout, "skip": False}


@pytest.fixture
def s3():
    fake = CacheFakeS3()
    state = {"v": 1, "title": "T", "design_system": "nocturne", "filename": "T.pptx", "pictures": [],
             "slides": [slide("s1", "one"), slide("s2", "two"), slide("s3", "three")]}
    fake.put(FOLDER + "/" + store.STATE_NAME, store.encode(state))
    return fake


def stored(s3):
    state, revision, _ = store.load(s3, BUCKET, DECK_KEY)
    return state, revision


def test_patch_updates_only_the_changed_slide_and_keeps_the_rest(s3):
    _, rev = stored(s3)
    patch = {"order": ["s1", "s2", "s3"], "slides": {"s2": slide("s2", "TWO")}}
    store.save(s3, BUCKET, DECK_KEY, rev, None, "req-00000001", patch=patch)
    state, _ = stored(s3)
    assert [s["html"] for s in state["slides"]] == ["<div>one</div>", "<div>TWO</div>", "<div>three</div>"]


def test_patch_adds_reorders_and_deletes_by_order(s3):
    _, rev = stored(s3)
    patch = {"order": ["s3", "new1", "s1"], "slides": {"new1": slide("new1", "fresh")}}
    store.save(s3, BUCKET, DECK_KEY, rev, None, "req-00000002", patch=patch)
    state, _ = stored(s3)
    assert [s["id"] for s in state["slides"]] == ["s3", "new1", "s1"]
    assert state["slides"][1]["html"] == "<div>fresh</div>"


def test_patch_only_validates_the_slides_it_sends(s3, monkeypatch):
    _, rev = stored(s3)
    checked = []
    real = store.safe_html
    monkeypatch.setattr(store, "safe_html", lambda html: checked.append(html) or real(html))
    patch = {"order": ["s1", "s2", "s3"], "slides": {"s1": slide("s1", "uno")}}
    store.save(s3, BUCKET, DECK_KEY, rev, None, "req-00000003", patch=patch)
    assert checked == ["<div>uno</div>"]


def test_patch_still_rejects_unsafe_html(s3):
    _, rev = stored(s3)
    bad = dict(slide("s1", "x"), html='<div><script>alert(1)</script></div>')
    with pytest.raises(store.EditorError):
        store.save(s3, BUCKET, DECK_KEY, rev, None, "req-00000004", patch={"order": ["s1"], "slides": {"s1": bad}})


def test_patch_naming_an_unknown_unsent_slide_is_a_conflict(s3):
    _, rev = stored(s3)
    with pytest.raises(store.Conflict):
        store.save(s3, BUCKET, DECK_KEY, rev, None, "req-00000005", patch={"order": ["s1", "ghost"], "slides": {}})


def test_patch_on_a_stale_revision_is_a_conflict(s3):
    with pytest.raises(store.Conflict):
        store.save(s3, BUCKET, DECK_KEY, "stale", None, "req-00000006",
                   patch={"order": ["s1", "s2", "s3"], "slides": {}})


def test_a_retried_patch_is_applied_once(s3):
    _, rev = stored(s3)
    patch = {"order": ["s1", "s2", "s3"], "slides": {"s1": slide("s1", "once")}}
    _, rev2 = store.save(s3, BUCKET, DECK_KEY, rev, None, "req-00000007", patch=patch)
    # The reply was lost; the editor resends the same batch with the old revision.
    _, rev3 = store.save(s3, BUCKET, DECK_KEY, rev, None, "req-00000007", patch=patch)
    assert rev3 == rev2


def test_full_state_saves_still_work(s3):
    state, rev = stored(s3)
    state["slides"][0]["html"] = "<div>full</div>"
    store.save(s3, BUCKET, DECK_KEY, rev, state, "req-00000008")
    assert stored(s3)[0]["slides"][0]["html"] == "<div>full</div>"


@pytest.mark.parametrize("patch", [[], {"order": "s1"}, {"order": ["s1"], "slides": []}, {"order": [1]}])
def test_malformed_patches_are_rejected(s3, patch):
    _, rev = stored(s3)
    with pytest.raises(store.EditorError):
        store.save(s3, BUCKET, DECK_KEY, rev, None, "req-00000009", patch=patch)
