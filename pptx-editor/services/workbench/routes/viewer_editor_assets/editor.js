(async () => {
  "use strict";
  const ownScript = document.currentScript,
    token = ownScript.dataset.token,
    base = new URL(ownScript.src).origin + "/artifacts/-/edit";
  const { Sortable, computePosition, flip, shift, offset, autoUpdate } =
    window.ViewerEditorLibraries;
  const stage = document.getElementById("stage"),
    rail = document.getElementById("rail"),
    originalImage = document.getElementById("slide"),
    exportMenu = document.getElementById("exportmenu"),
    exportRow = exportMenu?.querySelector(".row.build"),
    exportPdfLink = exportMenu?.querySelector("a.row");
  if (!stage || !rail) return;
  const uid = () => crypto.randomUUID().replaceAll("-", "");
  // One live deck state, used by the editing frames, the rail and the
  // persistence queue alike. Slides are replaced, never deep-copied: a
  // history snapshot copies only the slide objects (their HTML strings are
  // immutable and shared), so taking one costs O(slides), not O(deck bytes).
  const snap = (s) => ({ ...s, slides: s.slides.map((x) => ({ ...x })) });
  let state, revision, selectedId, selection = null, clipboard = null;

  // ---- TEMPORARY performance instrumentation ---------------------------
  // performance.mark/measure for every stage of an edit, with a one-line
  // console.debug summary. Filter the console on "[ve-perf]", or read
  // performance.getEntriesByType("measure"). Set PERF = false to silence.
  const PERF = true;
  let perfSeq = 0;
  function perfStart(name) {
    if (!PERF) return null;
    const id = "ve:" + name + ":" + ++perfSeq;
    performance.mark(id + ":start");
    return { name: "ve:" + name, id, t: performance.now() };
  }
  function perfEnd(p, detail = "") {
    if (!p) return;
    performance.mark(p.id + ":end");
    try {
      performance.measure(p.name, p.id + ":start", p.id + ":end");
    } catch {}
    performance.clearMarks(p.id + ":start");
    performance.clearMarks(p.id + ":end");
    if (performance.getEntriesByType("measure").length > 1000)
      performance.clearMeasures();
    console.debug("[ve-perf] " + p.name + " " + (performance.now() - p.t).toFixed(1) + "ms", detail);
  }

  async function api(path, options = {}) {
    const r = await fetch(base + path, { credentials: "omit", ...options });
    if (!r.ok) {
      let message = "Request failed (" + r.status + ").";
      try {
        const j = await r.json();
        message = j.detail || j.message || message;
      } catch {}
      const e = new Error(message);
      e.status = r.status;
      throw e;
    }
    return r;
  }
  const byId = (id) => state.slides.find((s) => s.id === id);
  const current = () => byId(selectedId);
  const say = (t) => {
    message.textContent = t || "";
  };
  function status(text, error = false) {
    savingLabel.textContent = text;
    savingLabel.dataset.error = error;
  }
  function button(text, title, action) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = text;
    b.title = title;
    b.setAttribute("aria-label", title);
    b.addEventListener("click", action);
    return b;
  }
  const tools = document.createElement("div");
  tools.className = "ve-tools";
  tools.setAttribute("role", "toolbar");
  tools.setAttribute("aria-label", "Insert and history");
  const savingLabel = document.createElement("span");
  savingLabel.className = "ve-save";
  savingLabel.setAttribute("role", "status");
  const message = document.createElement("div");
  message.className = "ve-message";
  message.setAttribute("role", "alert");
  stage.append(message);
  const format = document.createElement("div");
  format.className = "ve-format";
  format.hidden = true;
  format.setAttribute("role", "toolbar");
  format.setAttribute("aria-label", "Text and table formatting");
  const bottom = document.createElement("div");
  bottom.className = "ve-bottom";
  const notes = document.createElement("div");
  notes.className = "ve-notes";
  notes.hidden = true;
  notes.setAttribute("aria-label", "Speaker notes");
  let menu,
    menuCleanup = null,
    sortable = null;
  function closeMenu() {
    menuCleanup?.();
    menuCleanup = null;
    menu?.remove();
    menu = null;
  }
  function floatAt(anchor, panel) {
    return computePosition(anchor, panel, {
      strategy: "fixed",
      placement: "top-start",
      middleware: [offset(8), flip(), shift({ padding: 8 })],
    }).then(({ x, y }) =>
      Object.assign(panel.style, {
        position: "fixed",
        left: x + "px",
        top: y + "px",
      }),
    );
  }
  function placeFormat() {
    const wrap = active?.wrap;
    if (!selection?.rect || format.hidden || !wrap) return;
    const r = wrap.getBoundingClientRect(),
      s = r.width / 1920,
      b = selection.rect;
    floatAt(
      {
        getBoundingClientRect: () => ({
          x: r.x + b.x * s,
          y: r.y + b.y * s,
          left: r.x + b.x * s,
          top: r.y + b.y * s,
          right: r.x + (b.x + b.width) * s,
          bottom: r.y + (b.y + b.height) * s,
          width: b.width * s,
          height: b.height * s,
        }),
      },
      format,
    );
  }
  function popup(anchor, items) {
    closeMenu();
    menu = document.createElement("div");
    menu.className = "ve-menu";
    menu.setAttribute("role", "menu");
    for (const item of items) {
      const b = button(item.name, item.name, () => {
        closeMenu();
        Promise.resolve(item.run()).catch((e) => say(e.message));
      });
      b.disabled = !!item.disabled;
      b.setAttribute("role", "menuitem");
      menu.append(b);
    }
    document.getElementById("deck").append(menu);
    menuCleanup = autoUpdate(anchor, menu, () => floatAt(anchor, menu));
    menu.querySelector("button:not(:disabled)")?.focus();
    menu.addEventListener("keydown", (e) => {
      const a = [...menu.querySelectorAll("button:not(:disabled)")],
        i = a.indexOf(document.activeElement);
      if (["ArrowDown", "ArrowUp", "Home", "End", "Escape"].includes(e.key)) {
        e.preventDefault();
        e.stopPropagation();
        if (e.key === "Escape") {
          closeMenu();
          anchor.focus();
        } else
          a[
            e.key === "Home"
              ? 0
              : e.key === "End"
                ? a.length - 1
                : (i + (e.key === "ArrowDown" ? 1 : -1) + a.length) % a.length
          ]?.focus();
      }
    });
  }
  document.addEventListener("pointerdown", (e) => {
    if (menu && !menu.contains(e.target) && !e.target.closest(".ve-thumb-menu"))
      closeMenu();
  });

  // ---- Editing frames ---------------------------------------------------
  // A frame is booted once per layout (its design-system CSS is the only
  // thing that differs between layouts) and then reused: opening a slide
  // posts that slide's HTML from the live state into the frame. No iframe
  // reload, no server round trip, and no need for the slide to be saved
  // first - which is what lets a just-added slide be edited immediately.
  const MAX_FRAMES = 4,
    CANNOT_EDIT = "This slide's design cannot be edited in the browser editor.";
  const frames = new Map(); // layout -> frame record
  const frameWindows = new WeakSet(); // every frame window ever created
  let active = null, // the frame showing selectedId
    ready = false, // active frame has selectedId loaded
    useClock = 0;
  const assetBase = base + "/asset/" + token + "/",
    pictureBase = base + "/picture/" + token + "/";
  // Stored HTML <-> frame HTML. The frame resolves theme assets and pictures
  // through this editor's routes; stored HTML keeps `/ds/` and `../images/`.
  function normalizeHtml(text) {
    return text.replaceAll(assetBase, "/ds/").replaceAll(pictureBase, "../images/");
  }
  function frameHtml(text) {
    return text
      .replace(/\/ds\/([a-z0-9.-]+)\//g, (_, name) => assetBase + name + "/")
      .replaceAll("../images/", pictureBase);
  }
  function post(f, type, data = {}) {
    const msg = { ve: 1, type, ...data };
    if (f.shellReady) f.iframe.contentWindow.postMessage(msg, "*");
    else f.outbox.push(msg); // delivered, in order, the moment the frame boots
  }
  function frameFor(layout, warmOnly = false) {
    let f = frames.get(layout);
    if (f) {
      if (!warmOnly) f.lastUsed = ++useClock;
      return f;
    }
    if (frames.size >= MAX_FRAMES) {
      const victim = [...frames.values()]
        .filter((x) => x !== active)
        .sort((x, y) => x.lastUsed - y.lastUsed)[0];
      if (victim) dropFrame(victim);
    }
    const p = perfStart("frame-boot");
    f = {
      layout,
      sid: null,
      shellReady: false,
      loaded: false,
      readySid: null,
      outbox: [],
      lastUsed: warmOnly ? 0 : ++useClock,
      perf: p,
    };
    f.wrap = document.createElement("div");
    f.wrap.className = "ve-frame-wrap";
    f.wrap.style.visibility = "hidden";
    f.iframe = document.createElement("iframe");
    f.iframe.className = "ve-frame";
    f.iframe.title = "Editable slide";
    f.iframe.setAttribute("sandbox", "allow-scripts");
    f.iframe.src =
      base + "/shell/" + token + "?layout=" + encodeURIComponent(layout);
    f.wrap.append(f.iframe);
    stage.append(f.wrap);
    frameWindows.add(f.iframe.contentWindow);
    f.window = f.iframe.contentWindow;
    f.iframe.addEventListener("load", () =>
      setTimeout(() => {
        if (!f.shellReady && f === active)
          say(CANNOT_EDIT);
      }, 1500),
    );
    frames.set(layout, f);
    place();
    return f;
  }
  function dropFrame(f) {
    frames.delete(f.layout);
    // Pending HTML in that frame is flushed first; its "change" message is
    // still accepted after removal (frameWindows), so nothing is lost.
    if (f.shellReady && f.sid) post(f, "flush", { sid: f.sid });
    setTimeout(() => f.wrap.remove(), 2000);
  }
  function frameOf(source) {
    for (const f of frames.values()) if (f.window === source) return f;
    return null;
  }
  function send(type, data = {}) {
    if (!active || !active.sid) return;
    post(active, type, { sid: active.sid, ...data });
  }
  // Ask the active frame to hand over any HTML it is still holding back
  // (debounced typing). A local postMessage round trip - never a network
  // wait - and it gives up quietly rather than ever blocking the editor.
  const pendingSnapshots = new Map();
  function snapshot() {
    if (!active?.shellReady || !active.sid || !childPending.size)
      return Promise.resolve();
    const request = uid();
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        pendingSnapshots.delete(request);
        resolve();
      }, 1000);
      pendingSnapshots.set(request, () => {
        clearTimeout(timer);
        resolve();
      });
      send("snapshot", { request });
    });
  }
  function place() {
    if (!frames.size) return;
    const r = originalImage.getBoundingClientRect(),
      s = stage.getBoundingClientRect();
    let w = r.width,
      h = r.height;
    if (!w || !h) {
      w = stage.clientWidth - 24;
      h = (w * 1080) / 1920;
    }
    for (const f of frames.values()) {
      Object.assign(f.wrap.style, {
        left: r.left - s.left + "px",
        top: r.top - s.top + "px",
        width: w + "px",
        height: h + "px",
      });
      f.iframe.style.transform = "scale(" + w / 1920 + ")";
    }
    placeFormat();
  }
  function updateNotes() {
    if (notes.hidden) return;
    try {
      const d = new DOMParser().parseFromString(current().html, "text/html");
      notes.textContent =
        d.body.firstElementChild?.getAttribute("data-speaker-notes") ||
        "No speaker notes for this slide.";
    } catch {
      notes.textContent = "No speaker notes for this slide.";
    }
  }
  let switchPerf = null;
  // Synchronous: a slide switch never waits for a save, a render or the
  // network. Clicking another slide while one is still loading just loads
  // that one instead.
  function showSlide(id, { force = false } = {}) {
    const slide = byId(id);
    if (!slide) return;
    switchPerf = perfStart("slide-switch");
    historyBoundary();
    const previous = active;
    selectedId = id;
    selection = null;
    format.hidden = true;
    const f = frameFor(slide.layout || "");
    if (previous && previous !== f) {
      previous.wrap.style.visibility = "hidden";
      if (previous.sid) post(previous, "flush", { sid: previous.sid });
    }
    active = f;
    if (force || f.sid !== id) {
      ready = false;
      f.sid = id;
      f.readySid = null;
      post(f, "load", { sid: id, html: frameHtml(slide.html) });
    } else ready = f.readySid === id;
    if (f.loaded) f.wrap.style.visibility = "visible";
    const src = thumbSources.get(id);
    if (src && originalImage.src !== src) originalImage.src = src;
    originalImage.alt =
      "Slide " +
      (state.slides.findIndex((s) => s.id === id) + 1) +
      " of " +
      state.slides.length;
    place();
    updateRailSelection();
    updateNotes();
    if (ready) {
      perfEnd(switchPerf, "already loaded");
      switchPerf = null;
    }
  }
  // Boot frames for the neighbouring slides' layouts while idle, so moving
  // to a slide with a different layout is instant too.
  function warmNeighbours() {
    const idle = window.requestIdleCallback || ((fn) => setTimeout(fn, 200));
    idle(() => {
      const i = state.slides.findIndex((s) => s.id === selectedId);
      for (const n of [i + 1, i - 1]) {
        const s = state.slides[n];
        if (s && !frames.has(s.layout || "") && frames.size < MAX_FRAMES)
          frameFor(s.layout || "", true);
      }
    });
  }

  // ---- Undo / redo ------------------------------------------------------
  let undo = [],
    redo = [],
    historyTimer = null,
    historyPending = false,
    lastState;
  function historyBoundary() {
    clearTimeout(historyTimer);
    if (historyPending) {
      historyPending = false;
      undo.push(lastState);
      // Byte budget over the distinct HTML strings only: snapshots share
      // the strings of every slide that did not change between them.
      const budget = () => {
        const seen = new Set();
        let n = 0;
        for (const s of undo)
          for (const x of s.slides)
            if (!seen.has(x.html)) {
              seen.add(x.html);
              n += x.html.length;
            }
        return n;
      };
      while (undo.length > 30 || (undo.length > 1 && budget() > 48 * 1024 * 1024))
        undo.shift();
      lastState = snap(state);
      redo = [];
    }
    updateHistory();
  }
  function updateHistory() {
    undoButton.disabled = !undo.length;
    redoButton.disabled = !redo.length;
  }
  async function historyMove(isRedo) {
    await snapshot();
    historyBoundary();
    const from = isRedo ? redo : undo,
      to = isRedo ? undo : redo;
    if (!from.length) return;
    to.push(snap(state));
    const before = state;
    state = snap(from.pop());
    lastState = snap(state);
    // Only the slides that actually differ are persisted again.
    const old = new Map(before.slides.map((s) => [s.id, s]));
    for (const s of state.slides) {
      const o = old.get(s.id);
      if (!o || o.html !== s.html || o.skip !== s.skip || o.layout !== s.layout || o.name !== s.name)
        dirtySlides.add(s.id);
    }
    if (before.slides.map((s) => s.id).join() !== state.slides.map((s) => s.id).join())
      structureDirty = true;
    childPending.clear();
    for (const f of frames.values()) f.sid = null; // reload from the restored state when shown
    if (!byId(selectedId)) selectedId = state.slides[0].id;
    changed(false);
    updateRail();
    showSlide(selectedId, { force: true });
    updateHistory();
  }

  // ---- Persistence: dirty tracking + a single non-blocking save queue ----
  // An edit only ever does: update local state -> markDirty(slide) ->
  // scheduleSave(). persistChanges() runs later in the background, sends
  // just the dirty slides (plus the slide order), and never runs twice at
  // once; edits made while it is in flight stay local and go in the next one.
  const SAVE_DELAY = 800, // after the last edit
    SAVE_MAX_WAIT = 5000; // even during continuous editing
  const dirtySlides = new Set(),
    childPending = new Set(); // slides whose frame still holds unsent HTML
  let structureDirty = false,
    saving = false,
    saveAgain = false,
    saveTimer = null,
    firstUnsaved = 0,
    saveError = null,
    retryBatch = null,
    retryDelay = 0,
    retryTimer = null,
    lastSavedSlides = new Set();
  const hasDirty = () =>
    !!(dirtySlides.size || structureDirty || childPending.size || retryBatch);
  function markDirty(id) {
    if (id) dirtySlides.add(id);
  }
  function scheduleSave(delay = SAVE_DELAY) {
    clearTimeout(saveTimer);
    const now = performance.now();
    if (!firstUnsaved) firstUnsaved = now;
    delay = Math.max(0, Math.min(delay, firstUnsaved + SAVE_MAX_WAIT - now));
    saveTimer = setTimeout(persistChanges, delay);
  }
  function changed(history = true) {
    if (history) historyPending = true;
    lockExportControls();
    // After a conflict nothing more is sent; the edits stay local and the
    // conflict status (with its recovery download) stays visible.
    if (saveError?.status === 412) return;
    if (saveError) saveError = null;
    if (!saving) status("Unsaved changes");
    scheduleSave();
    clearTimeout(historyTimer);
    historyTimer = setTimeout(historyBoundary, 600);
  }
  function collectDirtyChanges() {
    if (!dirtySlides.size && !structureDirty) return null;
    const slides = {};
    for (const id of dirtySlides) {
      const s = byId(id);
      if (s) slides[id] = { id, name: s.name, html: s.html, layout: s.layout, skip: !!s.skip };
    }
    dirtySlides.clear();
    structureDirty = false;
    const request_id = uid();
    return {
      request_id,
      ids: Object.keys(slides),
      body: JSON.stringify({
        request_id,
        patch: { order: state.slides.map((s) => s.id), slides },
      }),
    };
  }
  async function persistChanges() {
    clearTimeout(saveTimer);
    saveTimer = null;
    if (saving) {
      saveAgain = true; // picked up as soon as the running save finishes
      return;
    }
    if (saveError?.status === 412) return; // a conflict needs the user, not a retry
    saving = true;
    let ok = true;
    try {
      // Pull in HTML still held back by the frame (debounced typing).
      if (childPending.size) await snapshot();
      // A failed batch is resent unchanged (same request_id) before anything
      // newer, so a save the server applied but whose reply was lost is
      // recognised as already done instead of being applied twice.
      const batch = retryBatch || collectDirtyChanges();
      if (batch) ok = await sendBatch(batch);
    } finally {
      saving = false;
    }
    if (!ok) return;
    saveAgain = false;
    if (dirtySlides.size || structureDirty || childPending.size) {
      // Edits arrived meanwhile: they go in the next save, after a pause.
      status("Unsaved changes");
      scheduleSave();
      return;
    }
    status("Saved");
    // Only once truly idle, so the export controls are never enabled
    // against a revision that is about to be superseded.
    syncExportControls();
    scheduleThumbs();
  }
  async function sendBatch(batch) {
    retryBatch = batch;
    firstUnsaved = 0;
    status("Saving…");
    const p = perfStart("save-request");
    try {
      const response = await api("/save/" + token, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "If-Match": '"' + revision + '"',
        },
        body: batch.body,
      });
      const result = await response.json();
      revision = result.revision;
      retryBatch = null;
      retryDelay = 0;
      saveError = null;
      retry.hidden = true;
      recovery.hidden = true;
      say("");
      for (const id of batch.ids) lastSavedSlides.add(id);
      perfEnd(p, batch.ids.length + " slide(s), " + batch.body.length + " bytes");
      return true;
    } catch (e) {
      perfEnd(p, "failed: " + e.message);
      fail(e);
      // Network errors and 5xx retry on their own with backoff; the edits
      // stay local and editable throughout.
      if (e.status === undefined || e.status >= 500) {
        retryDelay = Math.min(30000, (retryDelay || 1000) * 2);
        clearTimeout(retryTimer);
        retryTimer = setTimeout(persistChanges, retryDelay);
      }
      return false;
    }
  }
  // Exporting the ORIGINAL (unedited) file would be wrong for an editing
  // session, so the export row/link must point at this editor's own export
  // endpoint for the exact revision last confirmed saved - never at click
  // time (that would mean re-implementing the original menu's own click
  // handling), but kept fresh reactively, right after every save. While an
  // edit is unsaved or a save is in flight, the controls are disabled so the
  // original handler simply cannot fire with a URL older than what the user
  // just typed - see requirement 5's "never download a stale PPTX or PDF".
  function exportUrl(kind) {
    return base + "/export/" + token + "/" + kind + "?revision=" + encodeURIComponent(revision);
  }
  function lockExportControls() {
    if (exportRow) exportRow.disabled = true;
    if (exportPdfLink) exportPdfLink.setAttribute("aria-disabled", "true");
  }
  function syncExportControls() {
    if (exportRow) {
      exportRow.dataset.url = exportUrl("pptx");
      exportRow.disabled = false;
    }
    if (exportPdfLink) {
      exportPdfLink.href = exportUrl("pdf");
      exportPdfLink.removeAttribute("aria-disabled");
    }
  }
  function fail(e) {
    saveError = e;
    status(e.status === 412 ? "Conflict — edits kept" : "Save failed", true);
    say(e.message);
    recovery.hidden = false;
    retry.hidden = e.status === 412;
  }

  const undoButton = button("↶", "Undo", () => historyMove(false).catch(fail)),
    redoButton = button("↷", "Redo", () => historyMove(true).catch(fail));
  tools.append(
    button("T", "Insert text box", () => send("insert", { what: "text" })),
    button("Image", "Upload PNG or JPEG", () => upload.click()),
    button("Table", "Insert table", () => send("insert", { what: "table" })),
  );
  const shapes = button("Shapes ▾", "Insert shape", () =>
    popup(
      shapes,
      ["rectangle", "circle", "arrow"].map((what) => ({
        name: what[0].toUpperCase() + what.slice(1),
        run: () => send("insert", { what }),
      })),
    ),
  );
  tools.append(shapes, undoButton, redoButton, savingLabel);
  const retry = button("Retry", "Retry saving your changes", () => {
    clearTimeout(retryTimer);
    retryDelay = 0;
    if (saveError?.status !== 412) saveError = null;
    persistChanges();
  });
  tools.append(retry);
  retry.hidden = true;
  const recovery = button("Recovery", "Download your unsaved source", () => {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob([JSON.stringify(state, null, 2)], { type: "application/json" }),
    );
    a.download = "presentation-recovery.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  });
  recovery.hidden = true;
  tools.append(recovery);
  const upload = document.createElement("input");
  upload.type = "file";
  upload.accept = "image/png,image/jpeg";
  upload.hidden = true;
  upload.addEventListener("change", async () => {
    const file = upload.files[0];
    if (!file) return;
    try {
      if (file.size > 10 * 1024 * 1024)
        throw new Error("Images must be 10 MB or smaller.");
      const r = await api("/image/" + token, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: file,
      });
      send("insert", { what: "image", data: await r.json() });
    } catch (e) {
      say(e.message);
    }
    upload.value = "";
  });
  tools.append(upload);
  function formatControl(label, action) {
    return button(label, action, () => send("format", { action }));
  }
  const font = document.createElement("select");
  font.setAttribute("aria-label", "Font family");
  for (const name of [
    "Aeonik",
    "Aeonik Arabic",
    "Arial",
    "Calibri",
    "Aptos",
    "Times New Roman",
  ]) {
    const o = document.createElement("option");
    o.value = name;
    o.textContent = name;
    font.append(o);
  }
  font.onchange = () => send("format", { action: "font", value: font.value });
  const size = document.createElement("input");
  size.type = "number";
  size.min = "8";
  size.max = "240";
  size.setAttribute("aria-label", "Font size in slide pixels");
  size.onchange = () => send("format", { action: "size", value: size.value });
  const color = document.createElement("input");
  color.type = "color";
  color.setAttribute("aria-label", "Text color");
  color.oninput = () => send("format", { action: "color", value: color.value });
  format.append(
    font,
    size,
    color,
    formatControl("B", "bold"),
    formatControl("I", "italic"),
    formatControl("U", "underline"),
    formatControl("• List", "insertUnorderedList"),
    formatControl("Left", "justifyLeft"),
    formatControl("Center", "justifyCenter"),
    formatControl("Right", "justifyRight"),
  );
  for (const action of ["rows", "cols"]) {
    const label = document.createElement("label");
    label.textContent = action === "rows" ? "Rows " : "Columns ";
    label.dataset.tableControl = "true";
    const input = document.createElement("input");
    input.type = "number";
    input.min = "1";
    input.max = "20";
    input.value = action === "rows" ? "3" : "2";
    input.setAttribute(
      "aria-label",
      action === "rows" ? "Table rows" : "Table columns",
    );
    input.onchange = () => send("format", { action, value: input.value });
    label.append(input);
    format.append(label);
  }
  const link = document.createElement("input");
  link.type = "url";
  link.placeholder = "https://…";
  link.setAttribute("aria-label", "Link URL");
  link.hidden = true;
  format.append(
    link,
    button("Link", "Apply link to selected text", () => {
      if (link.hidden) { link.hidden = false; link.focus(); }
      else { send("format", { action: "link", value: link.value }); link.hidden = true; }
    }),
  );
  format.addEventListener("pointerdown", (e) => {
    if (e.target.tagName === "BUTTON") e.preventDefault();
  });
  bottom.append(
    button("+", "Add slide after", () =>
      operation("add", selectedId).catch((e) => say(e.message)),
    ),
    button("Notes", "Show or hide speaker notes", () => {
      notes.hidden = !notes.hidden;
      updateNotes();
    }),
  );
  stage.append(tools, format, bottom, notes);
  function placeholder() {
    return (
      "data:image/svg+xml," +
      encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="1920" height="1080" fill="white"/></svg>',
      )
    );
  }

  // ---- Rail -------------------------------------------------------------
  // updateRail() only for structural changes (add/delete/reorder/undo);
  // switching slides touches just the current marker and the counter.
  function updateRail() {
    const p = perfStart("rail-update");
    const existing = new Map(
      [...rail.children].map((el) => [el.dataset.id, el]),
    );
    const nodes = state.slides.map((slide, index) => {
      let thumb = existing.get(slide.id);
      if (!thumb) {
        thumb = document.createElement("button");
        thumb.type = "button";
        thumb.className = "thumb";
        thumb.dataset.id = slide.id;
        const img = document.createElement("img");
        img.width = 112;
        img.height = 63;
        img.alt = "";
        const number = document.createElement("span");
        number.className = "ve-number";
        const dots = document.createElement("span");
        dots.className = "ve-thumb-menu";
        dots.textContent = "⋯";
        dots.tabIndex = 0;
        dots.setAttribute("role", "button");
        dots.setAttribute("aria-haspopup", "menu");
        const show = (e) => {
          e.preventDefault();
          e.stopPropagation();
          slideMenu(dots, slide.id);
        };
        dots.addEventListener("click", show);
        dots.addEventListener("keydown", (e) => {
          if (["Enter", " "].includes(e.key)) show(e);
        });
        thumb.append(img, number, dots);
        thumb.addEventListener("click", () => showSlide(slide.id));
      }
      thumb.dataset.skipped = !!slide.skip;
      thumb.setAttribute("aria-label", "Slide " + (index + 1));
      const img = thumb.querySelector("img"),
        src = thumbSources.get(slide.id) || placeholder();
      if (img.getAttribute("src") !== src) img.src = src;
      thumb.querySelector(".ve-number").textContent = index + 1;
      thumb
        .querySelector(".ve-thumb-menu")
        .setAttribute("aria-label", "Slide " + (index + 1) + " options");
      return thumb;
    });
    if (nodes.length !== rail.children.length || nodes.some((n, i) => rail.children[i] !== n))
      rail.replaceChildren(...nodes);
    updateRailSelection();
    perfEnd(p, state.slides.length + " slides");
  }
  function updateRailSelection() {
    for (const thumb of rail.children)
      thumb.setAttribute("aria-current", thumb.dataset.id === selectedId ? "true" : "false");
    const index = state.slides.findIndex((s) => s.id === selectedId);
    document.getElementById("count").textContent =
      index + 1 + " / " + state.slides.length;
    document.getElementById("prev").disabled = index === 0;
    document.getElementById("next").disabled =
      index === state.slides.length - 1;
  }
  function createSortable() {
    // Created once: Sortable delegates on the rail, so it follows the
    // children as they are added, removed or reordered.
    sortable = Sortable.create(rail, {
      animation: 180,
      direction: "horizontal",
      draggable: ".thumb",
      dataIdAttr: "data-id",
      filter: ".ve-thumb-menu",
      preventOnFilter: false,
      ghostClass: "ve-sort-ghost",
      chosenClass: "ve-sort-chosen",
      forceFallback: true,
      fallbackOnBody: true,
      scroll: true,
      scrollSensitivity: 60,
      onEnd: () => {
        historyBoundary();
        const ids = sortable.toArray();
        const next = ids.map((id) => byId(id)).filter(Boolean);
        if (next.length !== state.slides.length) return updateRail();
        if (next.every((s, i) => s === state.slides[i])) return;
        state.slides = next;
        structureDirty = true;
        changed();
        historyBoundary();
        updateRail();
      },
    });
  }
  function slideMenu(anchor, id) {
    const i = state.slides.findIndex((s) => s.id === id),
      s = state.slides[i];
    popup(
      anchor,
      [
        ["Duplicate slide", "duplicate"],
        ["Copy slide", "copy"],
        ["Paste slide", "paste", !clipboard],
        ["Delete slide", "delete", state.slides.length === 1],
        [s.skip ? "Unskip slide" : "Skip slide", "skip"],
        ["Add slide after", "add"],
        ["Move left", "left", i === 0],
        ["Move right", "right", i === state.slides.length - 1],
      ].map(([name, op, disabled]) => ({
        name,
        disabled,
        run: () => operation(op, id),
      })),
    );
  }
  // Slide operations change the local state, mark what changed, schedule a
  // background save and update the view - in that order, with no await on
  // the network. A new slide is shown and editable before it is ever saved.
  async function operation(op, id) {
    const p = perfStart("slide-op:" + op);
    await snapshot(); // local only: picks up text still being typed
    historyBoundary();
    const i = state.slides.findIndex((s) => s.id === id),
      s = state.slides[i];
    if (!s) return;
    if (op === "copy") {
      clipboard = { ...s };
      say(
        "Slide copied inside this editor. It remains available after deleting the original.",
      );
      return;
    }
    if (["paste", "duplicate", "add"].includes(op) && state.slides.length >= 80)
      throw new Error("This editor supports up to 80 slides.");
    if (op === "delete" && state.slides.length <= 1) return;
    let reopen = false;
    if (op === "delete") {
      state.slides.splice(i, 1);
      dirtySlides.delete(id);
      childPending.delete(id);
      structureDirty = true;
      for (const f of frames.values()) if (f.sid === id) f.sid = null;
      releaseThumb(id);
      if (id === selectedId) {
        selectedId = state.slides[Math.min(i, state.slides.length - 1)].id;
        reopen = true;
      }
    } else if (op === "skip") {
      state.slides[i] = { ...s, skip: !s.skip };
      markDirty(id);
    } else if (op === "left" || op === "right") {
      const j = i + (op === "left" ? -1 : 1);
      if (j < 0 || j >= state.slides.length) return;
      [state.slides[i], state.slides[j]] = [state.slides[j], state.slides[i]];
      structureDirty = true;
    } else if (op === "paste" || op === "duplicate") {
      if (op === "paste" && !clipboard) return;
      const source = op === "paste" ? clipboard : s;
      const fresh = { ...source, id: uid() };
      fresh.name = "slide-" + fresh.id + ".html";
      state.slides.splice(i + 1, 0, fresh);
      markDirty(fresh.id);
      thumbSources.set(fresh.id, thumbSources.get(source.id) || placeholder());
      selectedId = fresh.id;
      reopen = true;
    } else if (op === "add") {
      const d = new DOMParser().parseFromString(s.html, "text/html"),
        root = d.body.firstElementChild;
      root.replaceChildren();
      root.removeAttribute("data-speaker-notes");
      root.removeAttribute("data-ve-id");
      root.style.position = "relative";
      root.style.width = "1920px";
      root.style.height = "1080px";
      const fresh = {
        id: uid(),
        name: "blank.html",
        layout: s.layout,
        html: root.outerHTML,
        skip: false,
      };
      state.slides.splice(i + 1, 0, fresh);
      markDirty(fresh.id);
      thumbSources.set(fresh.id, placeholder());
      selectedId = fresh.id;
      reopen = true;
    }
    changed();
    historyBoundary();
    updateRail();
    if (reopen) showSlide(selectedId);
    perfEnd(p);
  }

  // ---- Thumbnails (server-rendered, background only) --------------------
  // One thumbnail-loading path shared by the initial restore and every later
  // refresh: in-flight de-duplication (a second request for the same slide
  // reuses the first's promise instead of starting another), stale-response
  // rejection (a sequence number per slide; a response is only applied if no
  // newer request for that same slide has started since), and blob cleanup
  // (the previous object URL for a slide is revoked only once its
  // replacement has actually landed, so the rail never shows a blank frame).
  // A failure here is swallowed deliberately: it must never touch the save
  // state and so can never turn a successfully saved edit into an
  // apparently-unsaved one. Only slides that were actually saved are
  // re-rendered, never the whole deck.
  const thumbSources = new Map();
  const thumbBlobs = new Map();
  const thumbInFlight = new Map();
  const thumbSeq = new Map();
  let thumbCounter = 0,
    thumbTimer = null;
  function releaseThumb(sid) {
    thumbInFlight.delete(sid);
    thumbSeq.delete(sid);
    lastSavedSlides.delete(sid);
    const url = thumbBlobs.get(sid);
    if (url) {
      URL.revokeObjectURL(url);
      thumbBlobs.delete(sid);
    }
    thumbSources.delete(sid);
  }
  function fetchThumb(sid) {
    const existing = thumbInFlight.get(sid);
    if (existing) return existing;
    const seq = ++thumbCounter;
    thumbSeq.set(sid, seq);
    const promise = (async () => {
      const p = perfStart("thumbnail-render");
      try {
        const response = await api(
          "/thumbnail/" + token + "/" + sid + "?revision=" + encodeURIComponent(revision),
        );
        if (thumbSeq.get(sid) !== seq) return; // superseded while the request was in flight
        const blob = await response.blob();
        if (thumbSeq.get(sid) !== seq) return; // superseded while reading the body
        const url = URL.createObjectURL(blob);
        const previous = thumbBlobs.get(sid);
        thumbSources.set(sid, url);
        thumbBlobs.set(sid, url);
        const image = rail.querySelector('[data-id="' + sid + '"] img');
        if (image) image.src = url;
        if (sid === selectedId) originalImage.src = url;
        if (previous) URL.revokeObjectURL(previous);
      } catch {
        // Leave whatever thumbnail is already showing exactly as it was.
      } finally {
        thumbInFlight.delete(sid);
        perfEnd(p, sid.slice(0, 8));
      }
    })();
    thumbInFlight.set(sid, promise);
    return promise;
  }
  function scheduleThumbs() {
    clearTimeout(thumbTimer);
    thumbTimer = setTimeout(refreshThumbs, 1200);
  }
  async function refreshThumbs() {
    if (hasDirty() || saving) return; // the next save reschedules this
    const ids = [...lastSavedSlides].filter((id) => byId(id));
    lastSavedSlides.clear();
    let next = 0;
    async function worker() {
      while (next < ids.length) await fetchThumb(ids[next++]);
    }
    await Promise.all([worker(), worker()]);
  }
  async function restoreThumbnails() {
    const slides = state.slides;
    const POOL = 3; // bounded: studio itself is the scarce resource, not this tab
    let next = 0;
    async function worker() {
      while (next < slides.length) {
        if (hasDirty()) return;
        const slide = slides[next++];
        await fetchThumb(slide.id);
      }
    }
    await Promise.all(Array.from({ length: Math.min(POOL, slides.length) }, worker));
  }
  document.addEventListener(
    "click",
    (e) => {
      if (!state) return;
      const nav = e.target.closest("#prev,#next,#edge-prev,#edge-next");
      if (nav) {
        e.preventDefault();
        e.stopImmediatePropagation();
        const i = state.slides.findIndex((s) => s.id === selectedId),
          n = i + (nav.id.includes("prev") ? -1 : 1);
        if (state.slides[n]) showSlide(state.slides[n].id);
        return;
      }
      // #exportmenu's own row click (viewer.py's unmodified _EXPORT_SCRIPT)
      // is deliberately left to run on its own: it already shows "building…"
      // beside the label, keeps the menu open throughout, and restores menu
      // state on success or failure. All this editor does is keep
      // exportRow.dataset.url / exportPdfLink.href pointed at the latest
      // SAVED revision (syncExportControls, called after every save) and
      // disable both while a save is pending (lockExportControls, called
      // from changed()) - see the comment above exportUrl().
    },
    true,
  );
  document.addEventListener(
    "keydown",
    (e) => {
      if (!state) return;
      if (e.target.closest(".ve-menu")) {
        const items = [...menu.querySelectorAll("button:not(:disabled)")],
          i = items.indexOf(document.activeElement);
        if (["ArrowDown", "ArrowUp", "Home", "End", "Escape"].includes(e.key)) {
          e.preventDefault();
          if (e.key === "Escape") closeMenu();
          else
            items[
              e.key === "Home"
                ? 0
                : e.key === "End"
                  ? items.length - 1
                  : (i + (e.key === "ArrowDown" ? 1 : -1) + items.length) %
                    items.length
            ]?.focus();
        }
        e.stopImmediatePropagation();
        return;
      }
      if (e.target.closest(".ve-tools,.ve-format,.ve-bottom,.ve-notes")) {
        e.stopImmediatePropagation();
        return;
      }
      if (
        (e.ctrlKey || e.metaKey) &&
        ["z", "y"].includes(e.key.toLowerCase())
      ) {
        e.preventDefault();
        e.stopImmediatePropagation();
        historyMove(e.key.toLowerCase() === "y" || e.shiftKey).catch(fail);
        return;
      }
      const i = state.slides.findIndex((s) => s.id === selectedId);
      let n = null;
      if (["ArrowRight", "PageDown", " "].includes(e.key)) n = i + 1;
      else if (["ArrowLeft", "PageUp"].includes(e.key)) n = i - 1;
      else if (e.key === "Home") n = 0;
      else if (e.key === "End") n = state.slides.length - 1;
      if (n !== null) {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (state.slides[n]) showSlide(state.slides[n].id);
      }
    },
    true,
  );
  window.addEventListener("message", (e) => {
    const d = e.data;
    if (!frameWindows.has(e.source) || d?.ve !== 1) return;
    const f = frameOf(e.source);
    if (d.type === "shell") {
      if (!f) return;
      f.shellReady = true;
      perfEnd(f.perf, "layout " + (f.layout || "(default)"));
      for (const msg of f.outbox.splice(0)) f.window.postMessage(msg, "*");
      return;
    }
    // Content from any frame, even a hidden or retired one, is applied to
    // the slide it names: it is never dropped just because the user has
    // already moved on to another slide.
    if (d.type === "dirty") {
      if (!byId(d.sid)) return;
      childPending.add(d.sid);
      changed(false);
      return;
    }
    if (d.type === "change") {
      const slide = byId(d.sid);
      if (!slide) return;
      const p = perfStart("local-edit");
      const i = state.slides.indexOf(slide);
      state.slides[i] = { ...slide, html: normalizeHtml(d.html) };
      childPending.delete(d.sid);
      markDirty(d.sid);
      changed();
      perfEnd(p, d.html.length + " chars");
      return;
    }
    if (d.type === "snapshot") {
      pendingSnapshots.get(d.request)?.();
      pendingSnapshots.delete(d.request);
      return;
    }
    if (d.type === "ready" && f) {
      f.loaded = true;
      f.readySid = d.sid;
    }
    if (!f || f !== active || d.sid !== selectedId) return;
    if (d.type === "ready") {
      ready = true;
      f.wrap.style.visibility = "visible";
      if (message.textContent === CANNOT_EDIT) say("");
      place();
      if (switchPerf) {
        perfEnd(switchPerf, "slide rendered in frame");
        switchPerf = null;
      }
      warmNeighbours();
    } else if (d.type === "selection") {
      selection = d.selection;
      format.hidden = !selection || !["text", "table"].includes(selection.kind);
      if (selection) {
        if (document.activeElement !== size) size.value = Math.round(selection.size);
        if (![...font.options].some((o) => o.value === selection.font)) {
          const o = document.createElement("option");
          o.value = o.textContent = selection.font;
          font.append(o);
        }
        if (document.activeElement !== font) font.value = selection.font;
        format.querySelectorAll("[data-table-control]").forEach((x) => {
          x.hidden = selection.kind !== "table";
          if (!x.hidden)
            x.querySelector("input").value = x.textContent.startsWith("Rows")
              ? selection.rows
              : selection.cols;
        });
        placeFormat();
      }
    } else if (d.type === "undo" || d.type === "redo")
      historyMove(d.type === "redo").catch(fail);
  });
  window.addEventListener("beforeunload", (e) => {
    if (hasDirty() || saving) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
  new ResizeObserver(place).observe(stage);
  originalImage.addEventListener("load", place);
  document.addEventListener("fullscreenchange", place);
  try {
    status("Loading editor…");
    const r = await api("/state/" + token),
      data = await r.json();
    state = data.state;
    revision = data.revision;
    // The static markup's row/link still point at the ORIGINAL source's own
    // export, baked in before this editor attached - must be redirected to
    // this editor's own, revision-aware export before the menu is ever opened.
    syncExportControls();
    state.slides.forEach((s, i) => {
      const image = rail.children[i]?.querySelector("img");
      if (image && !state.request_id) thumbSources.set(s.id, image.src);
    });
    selectedId = state.slides[Math.min(state.slides.length-1, Math.max(0, Number(document.getElementById('deck').dataset.start || 1)-1))].id;
    lastState = snap(state);
    status("Saved");
    createSortable();
    updateRail();
    showSlide(selectedId);
    updateHistory();
    if (state.request_id) restoreThumbnails();
  } catch (e) {
    status("Editor unavailable", true);
    say(e.message);
    tools.remove();
    format.remove();
    bottom.remove();
    for (const f of frames.values()) f.wrap.remove();
  }
})();
