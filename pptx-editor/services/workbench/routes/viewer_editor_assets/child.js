(() => {
  "use strict";
  const { Moveable, Editor, Extension, StarterKit, TextStyleKit, TextAlign } =
    window.ViewerEditorLibraries;
  const { patches = [] } = window.VE_CONFIG;
  // The frame is a long-lived "shell": the parent swaps slides into it with a
  // `load` message instead of reloading the iframe for every slide. A frame
  // served by the legacy /frame/ route still starts with a slide in <body>.
  let sid = window.VE_CONFIG.sid || null;
  let root = sid
    ? [...document.body.children].find((el) => el.tagName !== "SCRIPT") || null
    : null;
  let selected = null,
    rich = null,
    textHost = null,
    beforeText = "",
    textChanged = false;
  let busy = false;
  const send = (type, data = {}) =>
    parent.postMessage({ ve: 1, sid, type, ...data }, "*");
  const uid = () => crypto.randomUUID().replaceAll("-", "");
  // TEMPORARY performance instrumentation (see editor.js's copy of this).
  const PERF = true;
  let perfSeq = 0;
  function perfStart(name) {
    if (!PERF) return null;
    const id = "ve:" + name + ":" + ++perfSeq;
    performance.mark(id + ":start");
    return { name: "ve:child:" + name, id, t: performance.now() };
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
  // Match the published corrections applied by Studio without editing the theme,
  // exactly as studio's patchSlide does: the slide's own root element included, and an
  // element that already is the corrected markup left alone. Returns the (possibly
  // replaced) root.
  const RUNTIME = ["data-ve-id", "data-deck-active", "data-om-validate", "data-dc-tpl", "data-dc-id", "data-deck-index", "slot", "aria-hidden", "inert"];
  function normal(el) {
    const copy = el.cloneNode(true);
    for (const e of [copy, ...copy.querySelectorAll("*")])
      for (const name of RUNTIME) e.removeAttribute(name);
    return copy.outerHTML.replace(/\s+/g, " ").trim();
  }
  function applyPatches(scope) {
    for (const patch of patches) {
      try {
        const template = document.createElement("template");
        template.innerHTML = String(patch.html || "").trim();
        const first = template.content.firstElementChild;
        const wanted = first ? normal(first) : null;
        const hits = [
          ...(scope.matches(patch.select) ? [scope] : []),
          ...scope.querySelectorAll(patch.select),
        ];
        for (const target of hits) {
          if (!target.parentNode || (wanted && normal(target) === wanted)) continue;
          if (target === scope) {
            if (!first) continue;
            const next = first.cloneNode(true);
            target.replaceWith(next);
            scope = next;
          } else target.replaceWith(template.content.cloneNode(true));
        }
      } catch {
        /* An optional invalid selector must not disable editing. */
      }
    }
    return scope;
  }
  function mark() {
    if (!root) return;
    for (const el of [root, ...root.querySelectorAll("*")])
      if (!el.dataset.veId && !el.closest(".tiptap")) el.dataset.veId = uid();
  }
  function textHTML() {
    if (!rich || !textChanged) return beforeText;
    const holder = document.createElement("div");
    holder.innerHTML = rich.getHTML();
    if (textHost?.matches('h1,h2,h3,h4,h5,h6,p')) {
      for (const paragraph of [...holder.children]) {
        if (paragraph.tagName !== 'P') continue;
        const span = document.createElement('span');
        span.style.cssText = paragraph.style.cssText;
        span.style.display = 'block';
        span.innerHTML = paragraph.innerHTML;
        paragraph.replaceWith(span);
      }
    }
    if (
      holder.children.length === 1 &&
      holder.firstElementChild.tagName === "P" &&
      !holder.firstElementChild.getAttribute("style")
    )
      return holder.firstElementChild.innerHTML;
    return holder.innerHTML;
  }
  function serialize() {
    const copy = root.cloneNode(true);
    if (textHost) {
      const host = copy.querySelector(
        '[data-ve-id="' + textHost.dataset.veId + '"]',
      );
      if (host) host.innerHTML = textHTML();
    }
    for (const el of [copy, ...copy.querySelectorAll("*")]) {
      el.removeAttribute("contenteditable");
      el.removeAttribute("spellcheck");
    }
    return copy.outerHTML;
  }
  // Edits stay local. The parent is told cheaply that this slide is dirty
  // right away, but the whole-slide serialization (a deep clone of the slide,
  // which can be large) and the postMessage of its HTML happen only once
  // typing pauses, or immediately for one-off actions such as drag end,
  // resize end, insert or delete.
  const CHANGE_DELAY = 300;
  let changeTimer = null,
    pending = false;
  function notify(immediate = false) {
    if (!root) return;
    if (!pending) send("dirty");
    pending = true;
    clearTimeout(changeTimer);
    if (immediate) flushChange();
    else changeTimer = setTimeout(flushChange, CHANGE_DELAY);
    scheduleUpdate();
  }
  function flushChange() {
    clearTimeout(changeTimer);
    changeTimer = null;
    if (!pending || !root) return;
    pending = false;
    const p = perfStart("serialize");
    mark();
    const html = serialize();
    perfEnd(p, html.length + " chars");
    send("change", { html });
  }
  // --- generic object classification, so every supported kind of slide
  // object (not only text in h1/p/li/blockquote) can be found, selected and
  // sized sensibly. Themes write many things - a classification bar, an
  // eyebrow label, a CSS-mask icon, a stroke-only decorative line - as plain
  // <div>/<span>/<svg> with no distinguishing tag or attribute, so these
  // helpers look at STRUCTURE (does it carry its own text? is it a leaf? is
  // it image-shaped?) rather than a fixed tag whitelist.
  function hasOwnText(el) {
    for (const node of el.childNodes)
      if (node.nodeType === 3 && node.textContent.trim()) return true;
    return false;
  }
  // A block-ish container that carries its OWN text directly (not just by
  // wrapping a heading/image/table) is being used as a text label, however
  // the theme tagged it - e.g. SAMI's `.classbar` ("Classification: <b>Public</b>"),
  // an eyebrow/kicker <div>. Matched by having its own text and no nested
  // structural object, not by tag name.
  function isTextBlock(el) {
    if (!(el instanceof Element) || el === root) return false;
    if (el.matches("h1,h2,h3,h4,h5,h6,p,li,blockquote")) return true;
    if (el.closest("table,svg,[data-ve-object]")) return false;
    if (!/^(block|flex|inline-block|grid|list-item)$/.test(getComputedStyle(el).display))
      return false;
    return hasOwnText(el) && !el.querySelector("img,svg,table,h1,h2,h3,h4,h5,h6,p,li,blockquote");
  }
  function climbToTextBlock(el) {
    for (let node = el; node && node !== root; node = node.parentElement)
      if (isTextBlock(node)) return node;
    return null;
  }
  // Image-shaped for resize purposes: a real <img>, a theme-drawn icon/logo
  // <svg> (not one this editor inserted as a freeform shape - those carry
  // data-ve-shape), or the CSS-mask icon pattern SAMI's capability icons use
  // (a childless span/div painted entirely by mask-image). Everything else
  // that is childless and textless (a line, a bar, a plain rule) is a "shape"
  // the user more often wants to stretch freely, not lock to its ratio.
  function looksLikeIcon(el) {
    if (el.tagName === "IMG") return true;
    if (el.tagName === "svg" && !el.dataset.veShape) return true;
    if (el.childElementCount === 0 && !hasOwnText(el)) {
      const cs = getComputedStyle(el);
      const masked = (v) => !!v && v !== "none";
      // Both the shorthand and the longhand, both prefixes: browsers differ
      // in which one they expand into `getComputedStyle`, so checking only
      // `maskImage` missed a shorthand `mask:` that a browser left on `.mask`.
      if (masked(cs.maskImage) || masked(cs.webkitMaskImage) || masked(cs.mask) || masked(cs.webkitMask))
        return true;
    }
    return false;
  }
  function type(el) {
    if (el.tagName === "TABLE") return "table";
    if (el.tagName === "IMG") return "image";
    if (el.matches("svg,[data-ve-shape]")) return "shape";
    if (el.childElementCount === 0 && !hasOwnText(el)) return "shape";
    return "text";
  }
  function findTarget(node) {
    const el = node instanceof Element ? node : node.parentElement;
    if (!el || !root.contains(el) || el === root) return null;
    return (
      el.closest("table") ||
      el.closest("svg") ||
      el.closest("[data-ve-object]") ||
      (el.tagName === "IMG" ? el : null) ||
      el.closest("h1,h2,h3,h4,h5,h6,p,li,blockquote") ||
      climbToTextBlock(el) ||
      // A leaf with no text of its own: an icon span, an <hr> line, a plain
      // decorative bar. No longer requires non-empty text - that requirement
      // is exactly what made icons and lines unselectable.
      (el.childElementCount === 0 ? el : null)
    );
  }
  // Every element `findTarget` would ever accept, used only as the geometric
  // fallback below - built once per pointer interaction (slides are small).
  function objectCandidates() {
    const found = new Set();
    for (const el of root.querySelectorAll("img,table,svg,[data-ve-object]")) {
      if (el.tagName !== "TABLE" && el.closest("table") && el.closest("table") !== el) continue;
      if (el.tagName !== "svg" && el.closest("svg") && el.closest("svg") !== el) continue;
      found.add(el);
    }
    for (const el of root.querySelectorAll("h1,h2,h3,h4,h5,h6,p,li,blockquote")) found.add(el);
    for (const el of root.querySelectorAll("*")) {
      if (found.has(el) || el.closest("table,svg,[data-ve-object]")) continue;
      if (isTextBlock(el)) found.add(el);
      else if (el.childElementCount === 0) found.add(el);
    }
    return [...found];
  }
  // A small invisible margin around small/thin objects, so the user does not
  // need to land exactly on a 2px-tall line or a thin SVG stroke: an outline
  // shape (fill:none) only receives pointer events on the stroke itself, so
  // a plain click-based hit test never reaches it at all without this.
  const MIN_HIT = 24;
  function expandedRect(el) {
    const r = el.getBoundingClientRect();
    const padX = Math.max(0, (MIN_HIT - r.width) / 2),
      padY = Math.max(0, (MIN_HIT - r.height) / 2);
    return {
      left: r.left - padX, right: r.right + padX,
      top: r.top - padY, bottom: r.bottom + padY,
      area: Math.max(r.width, 1) * Math.max(r.height, 1),
    };
  }
  function pointTarget(x, y) {
    let best = null, bestArea = Infinity;
    for (const el of objectCandidates()) {
      const r = expandedRect(el);
      if (x < r.left || x > r.right || y < r.top || y > r.bottom) continue;
      // Smallest matching candidate wins: a small icon sitting on a larger
      // card or background should be picked over the thing behind it.
      if (r.area < bestArea) { best = el; bestArea = r.area; }
    }
    return best;
  }
  function resolveTarget(event) {
    return findTarget(event.target) || pointTarget(event.clientX, event.clientY);
  }
  function selectionInfo() {
    if (!selected) {
      send("selection", { selection: null });
      return;
    }
    const rect = selected.getBoundingClientRect(),
      css = getComputedStyle(selected);
    send("selection", {
      selection: {
        kind: type(selected),
        font: css.fontFamily.split(",")[0].replaceAll('"', ""),
        size: parseFloat(css.fontSize),
        color: css.color,
        rows: selected.rows?.length,
        cols: selected.rows?.[0]?.cells.length,
        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
      },
    });
  }
  const mover = new Moveable(document.body, {
    target: null,
    draggable: true,
    resizable: true,
    snappable: true,
    origin: false,
    keepRatio: false,
    throttleDrag: 0,
    throttleResize: 0,
    renderDirections: ["nw", "n", "ne", "w", "e", "sw", "s", "se"],
    horizontalGuidelines: [0, 540, 1080],
    verticalGuidelines: [0, 960, 1920],
    snapThreshold: 7,
    checkInput: true,
  });
  function update() {
    mover.updateRect();
    selectionInfo();
  }
  // At most one rect update + selection report per animation frame, however
  // many keystrokes, pointermoves or caret moves arrive in between.
  let updateQueued = false;
  function scheduleUpdate() {
    if (updateQueued) return;
    updateQueued = true;
    requestAnimationFrame(() => {
      updateQueued = false;
      update();
    });
  }
  let selectionQueued = false;
  function scheduleSelectionInfo() {
    if (selectionQueued) return;
    selectionQueued = true;
    requestAnimationFrame(() => {
      selectionQueued = false;
      selectionInfo();
    });
  }
  function endText() {
    if (!rich) return;
    const host = textHost,
      value = textHTML();
    rich.destroy();
    rich = null;
    textHost = null;
    host.innerHTML = value;
    mover.draggable = true;
  }
  function select(el) {
    if (selected !== el) endText();
    selected = el;
    mover.target = el;
    mover.elementGuidelines = root
      ? [...root.children].filter((node) => node !== el)
      : [];
    mover.keepRatio = !!el && looksLikeIcon(el);
    // Larger resize handles for small objects (child.css's .ve-small-target
    // rule): a 18px handle is bigger than a thin line or a small icon, so the
    // handle itself becomes the easiest thing to grab instead of the object.
    const rect = el?.getBoundingClientRect();
    document.body.classList.toggle(
      "ve-small-target",
      !!rect && Math.min(rect.width, rect.height) < 40,
    );
    update();
  }
  const SlideHistory = Extension.create({
    name: "slideHistory",
    addKeyboardShortcuts() {
      return {
        Enter: () => this.editor.isActive('bulletList') || this.editor.isActive('orderedList') ? false : this.editor.commands.setHardBreak(),
        "Mod-z": () => {
          send("undo");
          return true;
        },
        "Mod-Shift-z": () => {
          send("redo");
          return true;
        },
        "Mod-y": () => {
          send("redo");
          return true;
        },
      };
    },
  });
  function edit(host) {
    if (!host || host === textHost) {
      rich?.commands.focus();
      return;
    }
    endText();
    beforeText = host.innerHTML;
    textChanged = false;
    textHost = host;
    const content = beforeText;
    host.replaceChildren();
    rich = new Editor({
      element: host,
      extensions: [
        StarterKit.configure({ undoRedo: false, link: { openOnClick: false } }),
        TextStyleKit,
        TextAlign.configure({ types: ["heading", "paragraph"] }),
        SlideHistory,
      ],
      content,
      editorProps: {
        attributes: { "aria-label": "Edit text", spellcheck: "true" },
      },
      onUpdate: () => {
        // Typing: local only. Serialization is debounced inside notify().
        textChanged = true;
        notify();
      },
      onSelectionUpdate: scheduleSelectionInfo,
    });
    mover.draggable = false;
    rich.commands.focus("end");
    update();
  }
  mover.on("dragStart", () => {
    endText();
    busy = true;
  });
  // pointerdown/pointermove: local movement only. pointerup (dragEnd /
  // resizeEnd): one change for the final geometry.
  mover.on("drag", (event) => {
    event.target.style.transform = event.transform;
    scheduleSelectionInfo();
  });
  mover.on("dragEnd", (event) => {
    busy = false;
    if (event.isDrag) notify(true);
  });
  mover.on("resizeStart", () => {
    endText();
    busy = true;
  });
  mover.on("resize", (event) => {
    Object.assign(event.target.style, {
      width: event.width + "px",
      height: event.height + "px",
      minWidth: "0",
      maxWidth: "none",
      boxSizing: "border-box",
      transform: event.drag.transform,
    });
    scheduleSelectionInfo();
  });
  mover.on("resizeEnd", (event) => {
    busy = false;
    if (event.isDrag) {
      if (selected && type(selected) === 'text') {
        selected.style.minHeight = selected.style.height;
        selected.style.height = 'auto';
      }
      notify(true);
    }
  });
  document.addEventListener("pointerdown", (event) => {
    if (!root) return;
    if (
      event.target.closest(".moveable-control-box") ||
      textHost?.contains(event.target)
    )
      return;
    const target = resolveTarget(event);
    if (!target) {
      select(null);
      return;
    }
    if (event.target.closest("a")) event.preventDefault();
    select(target);
  });
  document.addEventListener("dblclick", (event) => {
    if (!root) return;
    const target = resolveTarget(event);
    if (!target) return;
    select(target);
    const cell = event.target.closest("td,th");
    if (cell || type(target) === "text") edit(cell || target);
  });
  document.addEventListener("keydown", (event) => {
    if (!root) return;
    if (event.key === "Escape") {
      endText();
      select(null);
      return;
    }
    if (event.target.isContentEditable) return;
    if (
      (event.ctrlKey || event.metaKey) &&
      ["z", "y"].includes(event.key.toLowerCase())
    ) {
      event.preventDefault();
      send(event.key.toLowerCase() === "y" || event.shiftKey ? "redo" : "undo");
      return;
    }
    if (selected && ["Delete", "Backspace"].includes(event.key)) {
      event.preventDefault();
      selected.remove();
      select(null);
      notify(true);
    } else if (
      selected &&
      ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)
    ) {
      event.preventDefault();
      const n = event.shiftKey ? 10 : 1;
      mover.request(
        "draggable",
        {
          deltaX:
            event.key === "ArrowLeft" ? -n : event.key === "ArrowRight" ? n : 0,
          deltaY:
            event.key === "ArrowUp" ? -n : event.key === "ArrowDown" ? n : 0,
        },
        true,
      );
    } else if (
      selected &&
      ["Enter", "F2"].includes(event.key) &&
      type(selected) === "text"
    ) {
      event.preventDefault();
      edit(selected);
    }
  });
  function insert(what, data) {
    endText();
    const el =
      what === "image"
        ? document.createElement("img")
        : what === "table"
          ? document.createElement("table")
          : what === "arrow"
            ? document.createElementNS("http://www.w3.org/2000/svg", "svg")
            : document.createElement("div");
    el.dataset.veObject = what;
    el.dataset.veId = uid();
    Object.assign(el.style, {
      position: "absolute",
      left: "240px",
      top: "560px",
      width: "500px",
      boxSizing: "border-box",
      margin: "0",
      transform: "none",
    });
    if (getComputedStyle(root).position === "static")
      root.style.position = "relative";
    if (what === "text") {
      el.textContent = "Type your text";
      Object.assign(el.style, {
        fontSize: "40px",
        fontFamily: getComputedStyle(root).fontFamily,
        color: "#203b44",
        minHeight: "70px",
        overflowWrap: "break-word",
      });
    } else if (what === "image") {
      el.src = data.src;
      el.alt = "Uploaded image";
      el.style.height = (500 * data.size[1]) / data.size[0] + "px";
    } else if (what === "table") {
      el.style.borderCollapse = "collapse";
      el.style.fontSize = "32px";
      for (let r = 0; r < 3; r++) {
        const row = el.insertRow();
        for (let c = 0; c < 2; c++) {
          const cell = row.insertCell();
          cell.textContent = r ? "Text" : "Heading";
          Object.assign(cell.style, {
            border: "2px solid #78909c",
            padding: "12px",
            background: r ? "#ffffff" : "#e7eee9",
            color: "#203b44",
          });
        }
      }
    } else if (what === "arrow") {
      el.setAttribute("viewBox", "0 0 500 180");
      el.style.height = "180px";
      const path = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "path",
      );
      path.setAttribute("d", "M0 50 H330 V0 L500 90 L330 180 V130 H0 Z");
      path.setAttribute("fill", "#72be44");
      el.append(path);
      el.dataset.veShape = "arrow";
    } else {
      el.dataset.veShape = what;
      el.style.height = what === "circle" ? "500px" : "240px";
      el.style.background = "#72be44";
      if (what === "circle") el.style.borderRadius = "50%";
    }
    root.append(el);
    mark();
    select(el);
    notify(true);
    if (what === "text") edit(el);
  }
  function format(data) {
    if (!selected) return;
    const { action, value } = data;
    if (action === "rows" || action === "cols") {
      if (type(selected) !== "table") return;
      endText();
      const count = Math.max(1, Math.min(20, Number(value) || 1));
      if (action === "rows") {
        while (selected.rows.length > count) selected.deleteRow(-1);
        while (selected.rows.length < count) {
          const row = selected.rows[selected.rows.length - 1].cloneNode(true);
          for (const cell of row.cells) cell.textContent = "Text";
          for (const el of [row, ...row.querySelectorAll("*")])
            delete el.dataset.veId;
          (selected.tBodies[0] || selected).append(row);
        }
      } else
        for (const row of selected.rows) {
          while (row.cells.length > count) row.deleteCell(-1);
          while (row.cells.length < count) {
            const cell = row.cells[row.cells.length - 1].cloneNode(true);
            cell.textContent = "Text";
            delete cell.dataset.veId;
            row.append(cell);
          }
        }
      notify(true);
      return;
    }
    if (!rich) {
      if (type(selected) !== "text") return;
      edit(selected);
      rich.commands.selectAll();
    }
    const chain = rich.chain().focus();
    if (action === "bold") chain.toggleBold();
    else if (action === "italic") chain.toggleItalic();
    else if (action === "underline") chain.toggleUnderline();
    else if (action === "insertUnorderedList") chain.toggleBulletList();
    else if (action.startsWith("justify"))
      chain.setTextAlign(action.slice(7).toLowerCase());
    else if (action === "size")
      chain.setFontSize(Math.max(8, Math.min(240, Number(value))) + "px");
    else if (action === "font") chain.setFontFamily(value);
    else if (action === "color") chain.setColor(value);
    else if (action === "link" && /^https?:\/\//i.test(value))
      chain.setLink({ href: value });
    chain.run();
  }
  // Swap a slide into this already-booted frame: no iframe reload, no server
  // round trip, no re-initialisation of the editing libraries. The previous
  // slide's pending HTML is sent first, under its own id, so nothing typed
  // there is lost.
  const observer = new ResizeObserver(() => {
    if (!busy && root) scheduleUpdate();
  });
  let loadSeq = 0;
  function sendReady() {
    send("ready", {
      width: 1920,
      height: 1080,
      notes: root.getAttribute("data-speaker-notes") || "",
    });
  }
  function adopt(next) {
    if (root) observer.unobserve(root);
    root = applyPatches(next);
    mark();
    observer.observe(root);
  }
  function load(data) {
    const p = perfStart("load-slide");
    flushChange();
    endText();
    select(null);
    const template = document.createElement("template");
    template.innerHTML = data.html;
    const next = template.content.firstElementChild;
    if (!next) return;
    if (root) root.replaceWith(next);
    else document.body.prepend(next);
    sid = data.sid;
    adopt(next);
    const seq = ++loadSeq;
    // Wait for fonts only when they are still loading (normally the first
    // slide in a fresh frame); afterwards the slide is ready immediately.
    if (document.fonts.status === "loaded") sendReady();
    else
      document.fonts.ready.then(() => {
        if (seq === loadSeq) sendReady();
      });
    perfEnd(p, data.html.length + " chars");
  }
  window.addEventListener("message", (event) => {
    const data = event.data;
    if (event.source !== parent || data?.ve !== 1) return;
    if (data.type === "load") return load(data);
    if (data.sid !== sid) return;
    if (data.type === "insert") insert(data.what, data.data || {});
    else if (data.type === "format") format(data);
    else if (data.type === "flush") flushChange();
    else if (data.type === "snapshot") {
      // Any pending HTML goes out first as a normal "change"; postMessage
      // keeps order, so the parent has it before this acknowledgement.
      flushChange();
      send("snapshot", { request: data.request });
    }
  });
  if (root) {
    // Legacy /frame/ route: the slide was rendered into <body> by the server.
    adopt(root);
    document.fonts.ready.then(sendReady);
  } else send("shell");
})();
