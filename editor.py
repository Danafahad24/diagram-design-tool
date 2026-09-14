import base64
from html import escape

from canvas_diagram.models import CreateCanvasDiagramBody
from workspace_agent.common.links import public_base

MAXGRAPH_ASSET_VERSION = "8"


def build_canvas_editor_html(body: CreateCanvasDiagramBody) -> str:
    """Build the editable maxGraph diagram editor."""
    title = escape(body.title)
    graph_b64 = base64.b64encode(body.model_dump_json().encode("utf-8")).decode("ascii")
    maxgraph_url = f"{public_base()}/canvas-assets/maxgraph.bundle.js?v={MAXGRAPH_ASSET_VERSION}"
    template = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1" >
<title>__TITLE__</title>
<style>
:root {
  font-family:
    system-ui,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;
  color-scheme: light;
}
* {
  box-sizing: border-box;
}
html,
body {
  margin: 0;
  padding: 0;
  background: transparent;
}
button,
input,
select,
textarea {
  font: inherit;
}
button {
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  font-size: 12px;
  cursor: pointer;
}
button:hover:not(:disabled) {
  background: #f8fafc;
}
button:disabled {
  opacity: .45;
  cursor: not-allowed;
}
.diagram-shell {
  overflow: hidden;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: #ffffff;
  color: #0f172a;
}
.preview-view {
  padding: 24px;
  background: #050505;
}
.preview-frame {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 24px;
  border: 1px solid #27272a;
  border-radius: 16px;
  background: #050505;
}
.preview-image {
  display: block;
  width: 100%;
  max-width: 1100px;
  max-height: 540px;
  object-fit: contain;
}
.preview-actions {
  display: flex;
  justify-content: center;
  padding-top: 18px;
}
.edit-diagram-button {
  min-height: 44px;
  padding: 9px 20px;
  border: 1px solid #ffffff;
  border-radius: 10px;
  background: #ffffff;
  color: #000000;
  font-weight: 750;
}
.editor-view--preparing {
  position: fixed;
  left: -100000px;
  top: 0;
  width: 1200px;
  height: 760px;
  visibility: hidden;
  pointer-events: none;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  padding: 7px 10px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}
.toolbar-spacer {
  flex: 1 1 auto;
}
.toolbar-select {
  min-height: 34px;
  padding: 5px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  font-size: 11px;
}
.zoom-label {
  min-width: 50px;
  color: #64748b;
  font-size: 12px;
  text-align: center;
}
.workspace {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr) 250px;
  height: 610px;
  min-height: 460px;
}
.left-panel,
.right-panel {
  overflow-y: auto;
  padding: 12px;
  background: #ffffff;
}
.left-panel {
  border-right: 1px solid #e2e8f0;
}
.right-panel {
  border-left: 1px solid #e2e8f0;
}
.panel-title {
  margin: 0 0 10px;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}
.shape-search {
  width: 100%;
  min-height: 34px;
  margin-bottom: 10px;
  padding: 7px 9px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  color: #0f172a;
  font-size: 11px;
}
.section-title {
  margin: 16px 0 7px;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
}
.shape-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
}
.shape-button {
  min-height: 62px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 6px 4px;
}
.shape-symbol {
  font-size: 22px;
  line-height: 1;
}
.shape-name {
  font-size: 10px;
}
.shape-section[hidden],
.shape-button[hidden] {
  display: none !important;
}
.canvas-stage {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background-color: #f8fafc;
  background-image:
    linear-gradient(#dce3ec 1px, transparent 1px),
    linear-gradient(
      90deg,
      #dce3ec 1px,
      transparent 1px),
    linear-gradient(#eef2f7 1px, transparent 1px),
    linear-gradient(
      90deg,
      #eef2f7 1px,
      transparent 1px);
  background-size:
    50px 50px,
    50px 50px,
    10px 10px,
    10px 10px;
  touch-action: none;
}
#graph-container {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
  touch-action: none;
}
.properties-empty {
  color: #64748b;
  font-size: 11px;
  line-height: 1.5;
}
.property-group {
  margin-bottom: 11px;
}
.property-group label {
  display: block;
  margin-bottom: 4px;
  color: #64748b;
  font-size: 10px;
  font-weight: 650;
}
.property-group input,
.property-group select,
.property-group textarea {
  width: 100%;
  min-height: 32px;
  padding: 5px 7px;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  background: #ffffff;
  color: #0f172a;
}
.property-group textarea {
  min-height: 92px;
  resize: vertical;
}
.property-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 7px;
}
.property-check {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 11px;
  font-size: 11px;
}
.property-check input {
  width: auto;
}
.status {
  min-height: 31px;
  padding: 7px 11px;
  border-top: 1px solid #e2e8f0;
  color: #64748b;
  font-size: 11px;
}
.diagram-shell:fullscreen {
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100vh;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 0;
  border-radius: 0;
  background: #ffffff;
}
.diagram-shell:fullscreen .editor-view {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 0;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.diagram-shell:fullscreen .toolbar {
  flex: 0 0 auto;
}
.diagram-shell:fullscreen .workspace {
  flex: 1 1 0;
  width: 100%;
  height: 0;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.diagram-shell:fullscreen .left-panel,
.diagram-shell:fullscreen .right-panel,
.diagram-shell:fullscreen .canvas-stage {
  height: 100%;
  min-height: 0;
}
.diagram-shell:fullscreen .status {
  display: none;
}
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 130px minmax(0, 1fr);
  }
  .right-panel {
    display: none;
  }
  .shape-grid {
    grid-template-columns: 1fr;
  }
}
:root {
  --surface:#ffffff;
  --soft:#f8fafc;
  --ink:#0f172a;
  --muted:#475569;
  --border:#cbd5e1;
  --grid:#dce3ec;
  --fine:#eef2f7;
}
:root[data-theme=dark] {
  color-scheme: dark;
  --surface:#1e232b;
  --soft:#141820;
  --ink:#e5eaf3;
  --muted:#a8b5c8;
  --border:#3b4658;
  --grid:#293342;
  --fine:#1c2430;
}
.diagram-shell,
.left-panel,
.right-panel,
.toolbar,
.theme-bar {
  background: var(--surface);
  color: var(--ink);
  border-color: var(--border);
}
button,
input,
select,
textarea,
.toolbar-select,
.shape-search,
.property-group input,
.property-group textarea,
.property-group select {
  background: var(--surface);
  color: var(--ink);
  border-color: var(--border);
}
button:hover:not(:disabled) {
  background: var(--soft);
}
.panel-title,
.section-title,
.properties-empty,
.property-group label,
.zoom-label,
.status {
  color: var(--muted);
}
.status,
.preview-view,
.preview-frame {
  background: var(--soft);
  border-color: var(--border);
}
.theme-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  font-weight: 600;
}
.canvas-stage {
  background-color: var(--soft);
  background-image:
    linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(
      90deg,
      var(--grid) 1px,
      transparent 1px),
    linear-gradient(var(--fine) 1px, transparent 1px),
    linear-gradient(
      90deg,
      var(--fine) 1px,
      transparent 1px);
}
details.shape-section {
  border-bottom: 1px solid var(--border);
  padding: 4px 0;
}
details.shape-section summary {
  cursor: pointer;
  padding: 12px 0;
  font-size: 12px;
  font-weight: 600;
}
details.shape-section .shape-grid {
  padding-bottom: 10px;
}
.shape-symbol {
  width: 52px;
  height: 36px;
  display: grid;
  place-items: center;
  color: var(--ink);
}
.shape-symbol svg {
  max-width: 100%;
  max-height: 100%;
}
#shape-empty {
  color: var(--muted);
  font-size: 12px;
}
button:focus-visible,
summary:focus-visible {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}
</style>
</head>
<body>
<div id="diagram-shell" class="diagram-shell" >
<div class="theme-bar">
<span>Diagram Designer</span>
<button id="edit-diagram" type="button" aria-label="Expand diagram to edit" title="تكبير الرسم وتعديله" style="margin-left:auto;width:44px;height:40px">
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M3 3l6 6m12-6-6 6M3 21l6-6m12 6-6-6"/></svg></button>
</div>
<!-- Preview -->
<section id="preview-view" class="preview-view" >
<div class="preview-frame" >
<img id="preview-image" class="preview-image" alt="Diagram preview" >
</div>
</section>
<!-- Editor -->
<section id="editor-view" class=" editor-view editor-view--preparing " >
<div class="toolbar" >
<button id="undo" type="button" > Undo </button>
<button id="redo" type="button" > Redo </button>
<button id="duplicate" type="button" > Duplicate </button>
<button id="delete" type="button" > Delete </button>

<button id="layout-horizontal" type="button" > Auto H </button>
<button id="layout-vertical" type="button" > Auto V </button>
<button id="fit-view" type="button" > Fit </button>
<button id="export-svg" type="button" > Export SVG </button>
<button id="export-png" type="button" > Export PNG </button>
<span class="toolbar-spacer" >
</span>
<button id="zoom-out" type="button" > − </button>
<span id="zoom-label" class="zoom-label" > 100% </span>
<button id="zoom-in" type="button" > + </button>
</div>
<div class="workspace" >
<!-- Shapes -->
<aside class="left-panel" >
<h3 class="panel-title" > Shapes </h3>
<input id="shape-search" class="shape-search" placeholder="Search shapes..." >
<div id="shape-libraries">
</div>
<p id="shape-empty" hidden>No matching shapes.</p>
</aside>
<!-- Canvas -->
<main id="canvas-stage" class="canvas-stage" >
<div id="graph-container" >
</div>
</main>
<!-- Properties -->
<aside class="right-panel" >
<h3 class="panel-title" > Properties </h3>
<div id="properties-empty" class="properties-empty" > Select a shape or connection to edit its properties. </div>
<!-- Shape properties -->
<div id="vertex-properties" hidden >
<div class="property-group" >
<label for="property-text" > Text </label>
<textarea id="property-text" >
</textarea>
</div>
<div class="property-row" >
<div class="property-group" >
<label for="property-width" > Width </label>
<input id="property-width" type="number" min="40" >
</div>
<div class="property-group" >
<label for="property-height" > Height </label>
<input id="property-height" type="number" min="30" >
</div>
</div>
<div class="property-row" >
<div class="property-group" >
<label for="property-fill" > Fill </label>
<input id="property-fill" type="color" >
</div>
<div class="property-group" >
<label for="property-stroke" > Border </label>
<input id="property-stroke" type="color" >
</div>
</div>
<div class="property-row" >
<div class="property-group" >
<label for="property-font-color" > Text color </label>
<input id="property-font-color" type="color" >
</div>
<div class="property-group" >
<label for="property-font-size" > Font size </label>
<input id="property-font-size" type="number" min="8" max="72" >
</div>
</div>
<div class="property-group" >
<label for="property-rotation" > Rotation </label>
<input id="property-rotation" type="number" min="0" max="360" >
</div>
</div>
<div id="lane-properties" hidden>
  <h3 class="panel-title">Lanes</h3>
  <div class="property-row"><button id="add-lane" type="button">+ Add lane</button><button id="remove-lane" type="button">Remove lane</button></div>
  <div class="property-group"><label for="lane-selected">Selected lane</label><select id="lane-selected"></select></div>
  <div class="property-group"><label for="lane-name">Lane name</label><input id="lane-name" type="text" maxlength="80"></div>
  <p class="properties-empty">Dividers resize automatically. Removing a lane removes its divider and name, not diagram tasks.</p>
</div>
<div id="class-properties" hidden>
  <h3 class="panel-title">Class compartments</h3>
  <div class="property-group"><label for="class-name">Class name</label><input id="class-name" type="text"></div>
  <div class="property-group"><label for="class-attributes">Attributes (one per line)</label><textarea id="class-attributes"></textarea></div>
  <div class="property-group"><label for="class-methods">Operations (one per line)</label><textarea id="class-methods"></textarea></div>
</div>
<!-- Edge properties -->
<div id="edge-properties" hidden ><div class="property-group"><label for="edge-preset">Relationship</label><select id="edge-preset"><option value="">Custom</option><option value="association">UML association</option><option value="dependency">UML dependency</option><option value="inheritance">UML inheritance</option><option value="realization">UML realization</option><option value="aggregation">UML aggregation</option><option value="composition">UML composition</option><option value="sequence">BPMN sequence flow</option><option value="message">BPMN message flow</option><option value="oneMany">ER one to many</option><option value="manyMany">ER many to many</option><option value="bidirectional">Bidirectional</option></select></div>
<div class="property-row"><label><input id="edge-start-fill" type="checkbox">Fill start</label><label><input id="edge-end-fill" type="checkbox">Fill end</label></div>
<div class="property-row"><label>Start size<input id="edge-start-size" type="number" min="4" max="40" value="10"></label><label>End size<input id="edge-end-size" type="number" min="4" max="40" value="10"></label></div>
<div class="property-group" >
<label for="edge-label" > Label </label>
<input id="edge-label" type="text" >
</div>
<div class="property-group" >
<label for="edge-style" > Line type </label>
<select id="edge-style" >
<option value="straight" > Straight </option>
<option value="orthogonal" > Orthogonal </option>
<option value="elbow" > Elbow </option>
<option value="segmented" > Segmented </option>
<option value="curved" > Curved </option>
</select>
</div>
<div class="property-row" >
<div class="property-group" >
<label for="edge-start-arrow" > Start arrow </label>
<select id="edge-start-arrow" >
<option value="none"> None </option>
<option value="classic"> Classic </option>
<option value="block"> Block </option>
<option value="open"> Open </option>
<option value="diamond"> Diamond </option>
<option value="oval"> Oval </option><option value="classicThin">Classic thin</option><option value="blockThin">Triangle thin</option><option value="openThin">Open thin</option><option value="diamondThin">Diamond thin</option><option value="erOne">ER one</option><option value="erMany">ER many</option><option value="erZeroOne">ER zero or one</option><option value="erOneMany">ER one or many</option><option value="erZeroMany">ER zero or many</option>
</select>
</div>
<div class="property-group" >
<label for="edge-end-arrow" > End arrow </label>
<select id="edge-end-arrow" >
<option value="none"> None </option>
<option value="classic"> Classic </option>
<option value="block"> Block </option>
<option value="open"> Open </option>
<option value="diamond"> Diamond </option>
<option value="oval"> Oval </option><option value="classicThin">Classic thin</option><option value="blockThin">Triangle thin</option><option value="openThin">Open thin</option><option value="diamondThin">Diamond thin</option><option value="erOne">ER one</option><option value="erMany">ER many</option><option value="erZeroOne">ER zero or one</option><option value="erOneMany">ER one or many</option><option value="erZeroMany">ER zero or many</option>
</select>
</div>
</div>
<div class="property-row" >
<div class="property-group" >
<label for="edge-color" > Color </label>
<input id="edge-color" type="color" >
</div>
<div class="property-group" >
<label for="edge-width" > Width </label>
<input id="edge-width" type="number" min="1" max="12" >
</div>
</div>
<label class="property-check" >
<input id="edge-dashed" type="checkbox" > Dashed line </label>
</div>
</aside>
</div>
<div id="status" class="status" > Editor ready. </div>
</section>
<div id="icon-credits" style="padding:8px;font-size:11px;overflow-wrap:anywhere" hidden></div>
</div>
<script
    src="__MAXGRAPH_URL__"
>
</script> <script>
(() => {
  "use strict";
  let themedGraph = null;
  let hostTheme = null;
  function setTheme(theme) {
    if (!["light", "dark"].includes(theme)) return;
    document.documentElement.dataset.theme = theme;
    if (themedGraph) { themedGraph.refresh(); refreshPreview(); }
  }
  const systemTheme = matchMedia("(prefers-color-scheme: dark)");
  setTheme(systemTheme.matches ? "dark" : "light");
  systemTheme.addEventListener("change", () => {
    if (!hostTheme) setTheme(systemTheme.matches ? "dark" : "light");
  });
  // Host bridge is required for isolated/cross-origin Rich UI frames.
  window.addEventListener("message", (event) => {
    if (event.source !== parent || event.data?.type !== "canvas:theme") return;
    if (!["dark", "light"].includes(event.data.theme)) return;
    hostTheme = event.data.theme; setTheme(hostTheme);
  });
  parent.postMessage({type:"canvas:theme:request"}, "*");
  try {
    if (parent !== window) {
      const root = parent.document.documentElement;
      const sync = () => { hostTheme = root.classList.contains("dark") ? "dark" : "light"; setTheme(hostTheme); };
      sync(); new MutationObserver(sync).observe(root, {attributes:true, attributeFilter:["class"]});
    }
  } catch (_) { /* sandbox isolation: wait for the host bridge */ }
  const DEFAULT_FILL = "#ffffff";
  const DEFAULT_TEXT = "#000000";
  const DEFAULT_STROKE = "#334155";
  const DEFAULT_EDGE = "#475569";
  const diagramData = JSON.parse(
    new TextDecoder().decode(Uint8Array.from(atob("__GRAPH_B64__"), (c) => c.charCodeAt(0)))
  );
  const shell = document.getElementById(
    "diagram-shell"
  );
  const previewView = document.getElementById(
    "preview-view"
  );
  const previewImage = document.getElementById(
    "preview-image"
  );
  const editorView = document.getElementById(
    "editor-view"
  );
  const stage = document.getElementById(
    "canvas-stage"
  );
  const container = document.getElementById(
    "graph-container"
  );
  const status = document.getElementById(
    "status"
  );
  const undoButton = document.getElementById(
    "undo"
  );
  const redoButton = document.getElementById(
    "redo"
  );
  const duplicateButton = document.getElementById(
    "duplicate"
  );
  const deleteButton = document.getElementById(
    "delete"
  );
  const shapeSearch = document.getElementById(
    "shape-search"
  );
  const propertiesEmpty = document.getElementById(
    "properties-empty"
  );
  const vertexProperties = document.getElementById(
    "vertex-properties"
  );
  const edgeProperties = document.getElementById(
    "edge-properties"
  );
  const propertyText = document.getElementById(
    "property-text"
  );
  const propertyWidth = document.getElementById(
    "property-width"
  );
  const propertyHeight = document.getElementById(
    "property-height"
  );
  const propertyRotation = document.getElementById(
    "property-rotation"
  );
  const propertyFill = document.getElementById(
    "property-fill"
  );
  const propertyStroke = document.getElementById(
    "property-stroke"
  );
  const propertyFontColor = document.getElementById(
    "property-font-color"
  );
  const propertyFontSize = document.getElementById(
    "property-font-size"
  );
  const edgeLabel = document.getElementById(
    "edge-label"
  );
  const edgeStyle = document.getElementById(
    "edge-style"
  );
  const edgeStartArrow = document.getElementById(
    "edge-start-arrow"
  );
  const edgeEndArrow = document.getElementById(
    "edge-end-arrow"
  );
  const edgeColor = document.getElementById(
    "edge-color"
  );
  const edgeWidth = document.getElementById(
    "edge-width"
  );
  const edgeDashed = document.getElementById(
    "edge-dashed"
  );
  const renderer = window.CanvasDiagramMaxGraph;
  const requiredFunctions = ["createGraph", "createUndoManager", "getIconSvg", "getIconDataUri"];
  if (renderer?.BUNDLE_VERSION !== "8" || requiredFunctions.some(name => typeof renderer?.[name] !== "function")) {
    const message = document.createElement("div");
    message.setAttribute("role", "alert");
    message.style.cssText = "padding:20px;border:2px solid #ef4444;border-radius:10px;color:var(--ink);background:var(--surface);line-height:1.7";
    message.textContent = "The editor and renderer files do not match. This editor needs renderer v8. Rebuild index.js, replace canvas_diagram/assets/maxgraph.bundle.js, rebuild Workbench, and create a new diagram. الواجهة وملف الرسم غير متوافقين؛ أعيدي بناء ملف الرسم ووضعه في assets ثم أعيدي بناء Workbench وافتحي مخططًا جديدًا.";
    previewView.replaceChildren(message);
    editorView.remove();
    document.getElementById("edit-diagram").disabled = true;
    parent.postMessage({type:"iframe:height",height:document.documentElement.scrollHeight}, "*");
    return;
  }
  const graph = window.CanvasDiagramMaxGraph.createGraph(
    container
  );
  const baseCellStyle = graph.getCellStyle.bind(graph);
  graph.getCellStyle = (cell) => {
    const style = { ...baseCellStyle(cell) };
    if (document.documentElement.dataset.theme !== "dark") return style;
    const defaultFill = style.fillColor === DEFAULT_FILL;
    if (defaultFill) style.fillColor = "#242d3b";
    if (style.strokeColor === DEFAULT_STROKE || style.strokeColor === DEFAULT_EDGE) style.strokeColor = "#b8c8df";
    const outside = style.verticalLabelPosition === "bottom" || style.shape === "text" || cell.isEdge();
    if (style.fontColor === DEFAULT_TEXT && (defaultFill || outside)) style.fontColor = "#f1f5f9";
    if (["initial_state", "fork_join"].includes(style.diagramType) && style.fillColor === DEFAULT_STROKE) style.fillColor = "#b8c8df";
    if (style.image && ["user", "server", "api", "service", "queue", "code"].includes(style.diagramType)) {
      style.image = window.CanvasDiagramMaxGraph.getIconDataUri(style.diagramType, style.strokeColor);
    }
    return style;
  };
  themedGraph = graph;
  const undoManager = window.CanvasDiagramMaxGraph.createUndoManager(
    graph
  );
  const model = graph.getDataModel();
  const view = graph.getView();
  let newElementIndex = 0;
  let previewObjectUrl = null;
  function setStatus(message) {
    status.textContent = message;
  }
  function normalizeHex(value, fallback) {
    const text = String(
      value || ""
    ).trim();
    return /^#[0-9a-fA-F]{6}$/.test(
      text
    ) ? text : fallback;
  }
  function clampZoom(value) {
    return Math.max(
      0.2,
      Math.min(
        4,
        value
      )
    );
  }
  function updateZoomLabel() {
    document.getElementById(
      "zoom-label"
    ).textContent = Math.round(
      (view.scale || 1) * 100
    ) + "%";
  }
  function lineTypeFromStyle(style) {
    if (style.curved) {
      return "curved";
    }
    switch (style.edgeStyle) {
      case "orthogonalEdgeStyle":
        return "orthogonal";
      case "elbowEdgeStyle":
        return "elbow";
      case "segmentEdgeStyle":
        return "segmented";
      default:
        return "straight";
    }
  }
  function applyLineType(style, lineType) {
    style.curved = false;
    style.bendable = true;
    switch (lineType) {
      case "orthogonal":
        style.edgeStyle = "orthogonalEdgeStyle";
        break;
      case "elbow":
        style.edgeStyle = "elbowEdgeStyle";
        break;
      case "segmented":
        style.edgeStyle = "segmentEdgeStyle";
        break;
      case "curved":
        delete style.edgeStyle;
        style.curved = true;
        break;
      default:
        delete style.edgeStyle;
    }
  }
  function applyIconLabelStyle(style, iconName) {
    const image = window.CanvasDiagramMaxGraph.getIconDataUri?.(
      iconName,
      DEFAULT_STROKE
    );
    style.shape = "label";
    style.rounded = true;
    style.arcSize = 12;
    style.spacing = 8;
    style.spacingLeft = 42;
    style.align = "left";
    if (image) {
      style.image = image;
      style.imageWidth = 28;
      style.imageHeight = 28;
      style.imageAlign = "left";
    }
  }
  function vertexStyleFor(element) {
    const style = {
      fillColor: element.style?.fill || DEFAULT_FILL,
      strokeColor: element.style?.stroke || DEFAULT_STROKE,
      strokeWidth: element.style?.stroke_width ?? 2,
      fontColor: element.style?.font_color || DEFAULT_TEXT,
      fontSize: element.style?.font_size || 14,
      whiteSpace: "wrap",
      overflow: "hidden",
      align: "center",
      verticalAlign: "middle",
      rotation: Number(
        element.rotation || 0
      )
    };
    switch (element.type) {
      case "rounded_rectangle":
        style.shape = "rectangle";
        style.rounded = true;
        style.arcSize = 18;
        break;
      case "circle":
        style.shape = "ellipse";
        style.aspect = "fixed";
        break;
      case "ellipse":
      case "start_end":
        style.shape = "ellipse";
        break;
      case "diamond":
      case "decision":
        style.shape = "rhombus";
        break;
      case "triangle":
        style.shape = "triangle";
        break;
      case "hexagon":
      case "data":
        style.shape = "hexagon";
        break;
      case "double_ellipse":
        style.shape = "doubleEllipse";
        break;
      case "database":
        style.shape = "cylinder";
        break;
      case "actor":
        style.shape = "actor";
        break;
      case "cloud":
        style.shape = "cloud";
        break;
      case "process":
        style.shape = "rectangle";
        break;
      case "subprocess":
        style.shape = "rectangle";
        style.strokeWidth = Math.max(
          3,
          Number(
            style.strokeWidth || 2
          )
        );
        break;
      case "document":
        applyIconLabelStyle(
          style,
          "document"
        );
        break;
      case "user":
        applyIconLabelStyle(
          style,
          "user"
        );
        break;
      case "server":
        applyIconLabelStyle(
          style,
          "server"
        );
        break;
      case "api":
        applyIconLabelStyle(
          style,
          "api"
        );
        break;
      case "service":
        applyIconLabelStyle(
          style,
          "service"
        );
        break;
      case "queue":
        applyIconLabelStyle(
          style,
          "queue"
        );
        break;
      case "code":
        applyIconLabelStyle(
          style,
          "code"
        );
        break;
      case "container":
      case "swimlane":
        style.shape = "swimlane";
        style.horizontal = true;
        style.startSize = 28;
        break;
      /*
       * IMPORTANT ERD FIX
       *
       * Class / Entity / Table
       * are NOT swimlanes anymore.
       *
       * Therefore:
       * - the entire box is editable
       * - the entire box is resizable
       * - multiline text works
       */
      case "class":
      case "entity":
      case "table":
        style.shape = "rectangle";
        style.rounded = false;
        style.align = "left";
        style.verticalAlign = "top";
        style.spacing = 10;
        break;
      case "text":
        style.shape = "text";
        style.fillColor = "none";
        style.strokeColor = "none";
        break;
      default:
        style.shape = "rectangle";
    }
    style.diagramType = element.type;
    const notation = [
      "actor",
      "data",
      "document",
      "subprocess",
      "class",
      "entity",
      "table",
      "note",
      "package",
      "lifeline",
      "bpmn_start_event",
      "bpmn_intermediate_event",
      "bpmn_end_event",
      "bpmn_exclusive_gateway",
      "bpmn_parallel_gateway",
      "bpmn_inclusive_gateway",
      "bpmn_subprocess",
      "final_state"
    ];
    if (notation.includes(element.type)) {
      style.shape = "diagramNotation";
      delete style.image;
      delete style.spacingLeft;
      style.rounded = false;
      style.align = "center";
    }
    if (element.type === "subprocess") {
      style.spacingLeft = element.width * 0.14;
      style.spacingRight = element.width * 0.14;
      style.strokeWidth = element.style?.stroke_width ?? 2;
    }
    if (element.type === "use_case") style.shape = "ellipse";
    if ([
      "actor",
      "bpmn_start_event",
      "bpmn_intermediate_event",
      "bpmn_end_event",
      "bpmn_exclusive_gateway",
      "bpmn_parallel_gateway",
      "bpmn_inclusive_gateway"
    ].includes(element.type)) {
      style.verticalLabelPosition = "bottom";
      style.verticalAlign = "top";
      style.spacingTop = 6;
      style.overflow = "visible";
    }
    if (element.type === "start_end" || element.type === "bpmn_task") {
      style.shape = "rectangle";
      style.rounded = true;
      style.arcSize = element.type === "start_end" ? 100 : 16;
    }
    if (["pool", "system_boundary"].includes(element.type)) {
      style.shape = "swimlane";
      style.horizontal = element.type !== "pool";
      style.startSize = 30;
    }
    if (["initial_state", "fork_join"].includes(element.type)) {
      style.shape = element.type === "initial_state" ? "ellipse" : "rectangle";
      style.fillColor = style.strokeColor;
    }
    if (element.type === "lifeline") {
      style.verticalAlign = "top";
      style.spacingTop = 8;
    }
    if (["pool", "swimlane"].includes(element.type)) {
      style.shape = "diagramNotation";
      style.laneLabels = JSON.stringify(element.lanes?.length ? element.lanes : ["Lane 1","Lane 2","Lane 3"]);
    }
    if (element.type === "image") {
      style.shape = "image"; style.image = element.image_data || "";
      style.imageAspect = true; style.verticalLabelPosition = "bottom"; style.verticalAlign = "top";
    }
    return style;
  }
  function edgeStyleFor(connection = null) {
    const requested = connection?.style || {};
    const style = {
      endArrow: requested.end_arrow || "classic",
      startArrow: requested.start_arrow || "none",
      startFill: requested.start_fill ?? true, endFill: requested.end_fill ?? true,
      startSize: requested.start_size ?? 10, endSize: requested.end_size ?? 10,
      strokeColor: requested.stroke || DEFAULT_EDGE,
      strokeWidth: requested.stroke_width ?? 2,
      dashed: Boolean(
        requested.dashed
      ),
      fontColor: DEFAULT_TEXT,
      fontSize: 12,
      rounded: true,
      bendable: true
    };
    applyLineType(
      style,
      requested.line_type || "orthogonal"
    );
    return style;
  }
  function loadDiagram() {
    graph.batchUpdate(
      () => {
        for (const element of diagramData.elements || []) {
          graph.insertVertex({
            id: "vertex:" + element.id,
            value: element.text || "",
            position: [
              Number(
                element.x
              ) || 0,
              Number(
                element.y
              ) || 0
            ],
            size: [
              Math.max(
                1,
                Number(
                  element.width
                ) || 160
              ),
              Math.max(
                1,
                Number(
                  element.height
                ) || 80
              )
            ],
            style: vertexStyleFor(
              element
            )
          });
        }
        const containers = graph.getChildVertices(graph.getDefaultParent()).filter(cell =>
          ["pool","swimlane","system_boundary","container"].includes(cell.style?.diagramType));
        if (containers.length) graph.orderCells(true, containers);
        for (const connection of diagramData.connections || []) {
          const source = model.getCell(
            "vertex:" + connection.source
          );
          const target = model.getCell(
            "vertex:" + connection.target
          );
          if (!source || !target) {
            continue;
          }
          graph.insertEdge({
            id: "edge:" + connection.id,
            source,
            target,
            value: connection.label || "",
            style: edgeStyleFor(
              connection
            )
          });
        }
      }
    );
  }
  function addElement(type, text, width = 160, height = 80) {
    newElementIndex += 1;
    const offset = (newElementIndex % 6) * 18;
    const origin = view.getTranslate();
    const scale = view.scale || 1;
    const element = {
      id: "element-" + crypto.randomUUID(),
      type,
      x: (90 + offset) / scale - origin.x,
      y: (90 + offset) / scale - origin.y,
      width,
      height,
      rotation: 0,
      text,
      style: {
        fill: DEFAULT_FILL,
        stroke: DEFAULT_STROKE,
        font_color: DEFAULT_TEXT,
        font_size: 14
      }
    };
    let cell;
    graph.batchUpdate(
      () => {
        cell = graph.insertVertex({
          id: "vertex:" + element.id,
          value: element.text,
          position: [
            element.x,
            element.y
          ],
          size: [
            width,
            height
          ],
          style: vertexStyleFor(
            element
          )
        });
      }
    );
    if (["pool", "swimlane", "system_boundary", "container"].includes(type)) graph.orderCells(true, [cell]);
    graph.setSelectionCell(
      cell
    );
    syncProperties();
    setStatus(
      type + " added."
    );
  }
  function updateUndoButtons() {
    undoButton.disabled = !undoManager.canUndo();
    redoButton.disabled = !undoManager.canRedo();
  }
  function duplicateSelected() {
    const cells = graph.getSelectionCells();
    if (!cells.length) {
      return;
    }
    const clones = graph.moveCells(
      cells,
      24,
      24,
      true
    );
    if (clones?.length) {
      graph.setSelectionCells(
        clones
      );
    }
    syncProperties();
    updateUndoButtons();
    setStatus(
      "Selection duplicated."
    );
  }
  function applyAutomaticLayout(direction) {
    window.CanvasDiagramMaxGraph.applyAutoLayout(
      graph,
      direction
    );
    fitView();
    updateUndoButtons();
    setStatus(
      direction === "vertical" ? "Vertical automatic layout applied." : "Horizontal automatic layout applied."
    );
  }
  function deleteSelected() {
    const cells = graph.getSelectionCells();
    if (!cells.length) {
      return;
    }
    graph.removeCells(
      cells,
      true
    );
    syncProperties();
    updateUndoButtons();
    setStatus(
      "Selection deleted."
    );
  }
  const lanePanel = document.getElementById("lane-properties");
  const classPanel = document.getElementById("class-properties");
  const laneSelect = document.getElementById("lane-selected");
  const laneName = document.getElementById("lane-name");
  const className = document.getElementById("class-name");
  const classAttributes = document.getElementById("class-attributes");
  const classMethods = document.getElementById("class-methods");
  const isLaneContainer = cell => ["pool","swimlane"].includes(cell?.style?.diagramType);
  function laneNames(cell) {
    try { const names = JSON.parse(cell.style.laneLabels || "[]"); if (Array.isArray(names) && names.length) return names; } catch (_) {}
    return ["Lane 1","Lane 2","Lane 3"];
  }
  function updateLaneNames(names, selectedIndex) {
    const cell = graph.getSelectionCell();
    if (!isLaneContainer(cell)) return;
    graph.batchUpdate(() => {
      const style = cell.getClonedStyle(); style.laneLabels = JSON.stringify(names);
      model.setStyle(cell, style);
      const geometry = cell.getGeometry().clone();
      geometry.height = Math.max(geometry.height, names.length * 60 + (style.diagramType === "swimlane" ? 32 : 0));
      model.setGeometry(cell, geometry);
    });
    syncProperties();
    laneSelect.value = String(Math.min(selectedIndex, names.length-1));
    laneName.value = names[Number(laneSelect.value)];
  }
  document.getElementById("add-lane").addEventListener("click", () => {
    const cell = graph.getSelectionCell(); if (!isLaneContainer(cell)) return;
    const names = laneNames(cell); if (names.length >= 12) return;
    let index = names.length+1; while (names.includes("Lane " + index)) index++;
    names.push("Lane " + index); updateLaneNames(names, names.length-1);
  });
  document.getElementById("remove-lane").addEventListener("click", () => {
    const cell = graph.getSelectionCell(); if (!isLaneContainer(cell)) return;
    const names = laneNames(cell); if (names.length <= 1) return;
    const index = Number(laneSelect.value); names.splice(index,1); updateLaneNames(names,index);
  });
  laneSelect.addEventListener("change", () => { const cell = graph.getSelectionCell(); if (isLaneContainer(cell)) laneName.value = laneNames(cell)[Number(laneSelect.value)]; });
  laneName.addEventListener("change", () => {
    const cell = graph.getSelectionCell(); if (!isLaneContainer(cell)) return;
    const names = laneNames(cell); const index = Number(laneSelect.value);
    names[index] = laneName.value.trim() || "Lane " + (index+1); updateLaneNames(names,index);
  });
  function splitClass(value) {
    const rows = String(value || "").split("\n"); const name = rows.shift() || "Class";
    let separator = rows.findIndex(row => row.trim() === "---");
    if (separator < 0) { separator = rows.findIndex(row => row.includes("(")); if (separator < 0) separator = rows.length; }
    return {name, attributes:rows.slice(0,separator).join("\n").trim(), methods:rows.slice(separator + (rows[separator]?.trim() === "---" ? 1 : 0)).join("\n").trim()};
  }
  for (const input of [className,classAttributes,classMethods]) input.addEventListener("change", () => {
    const cell = graph.getSelectionCell(); if (cell?.style?.diagramType !== "class") return;
    graph.batchUpdate(() => {
      model.setValue(cell, [className.value || "Class", classAttributes.value, "---", classMethods.value].join("\n"));
      const geometry = cell.getGeometry().clone();
      const rows = classAttributes.value.split("\n").length + classMethods.value.split("\n").length;
      geometry.height = Math.max(geometry.height, 32 + rows * Math.max(20,Number(cell.style.fontSize || 14)*1.5));
      model.setGeometry(cell,geometry);
    });
    syncProperties();
  });
  function syncProperties() {
    const cell = graph.getSelectionCell();
    const selectedCells = graph.getSelectionCells();
    lanePanel.hidden = !isLaneContainer(cell);
    classPanel.hidden = cell?.style?.diagramType !== "class";
    if (!lanePanel.hidden) {
      const selected = Number(laneSelect.value || 0); const names = laneNames(cell);
      laneSelect.replaceChildren(...names.map((name,index) => { const option = document.createElement("option"); option.value=String(index); option.textContent=name; return option; }));
      laneSelect.value = String(Math.min(selected,names.length-1)); laneName.value = names[Number(laneSelect.value)];
      document.getElementById("add-lane").disabled = names.length >= 12;
      document.getElementById("remove-lane").disabled = names.length <= 1;
    }
    if (!classPanel.hidden) {
      const parts = splitClass(cell.value); className.value=parts.name; classAttributes.value=parts.attributes; classMethods.value=parts.methods;
    }
    deleteButton.disabled = !cell;
    duplicateButton.disabled = selectedCells.length === 0;
    propertiesEmpty.hidden = Boolean(
      cell
    );
    vertexProperties.hidden = true;
    edgeProperties.hidden = true;
    if (!cell) {
      return;
    }
    if (cell.isVertex()) {
      vertexProperties.hidden = false;
      const geometry = cell.getGeometry();
      const style = baseCellStyle(
        cell
      );
      propertyText.value = String(
        cell.getValue() ?? ""
      );
      propertyWidth.value = Math.round(
        geometry?.width || 160
      );
      propertyHeight.value = Math.round(
        geometry?.height || 80
      );
      propertyRotation.value = Math.round(
        Number(
          style.rotation || 0
        )
      );
      propertyFill.value = normalizeHex(
        style.fillColor,
        DEFAULT_FILL
      );
      propertyStroke.value = normalizeHex(
        style.strokeColor,
        DEFAULT_STROKE
      );
      propertyFontColor.value = normalizeHex(
        style.fontColor,
        DEFAULT_TEXT
      );
      propertyFontSize.value = Math.round(
        Number(
          style.fontSize || 14
        )
      );
      return;
    }
    if (cell.isEdge()) {
      edgeProperties.hidden = false;
      const style = baseCellStyle(
        cell
      );
      edgeLabel.value = String(
        cell.getValue() ?? ""
      );
      edgeStyle.value = lineTypeFromStyle(
        style
      );
      edgeStartArrow.value = style.startArrow || "none";
      edgeEndArrow.value = style.endArrow || "none";
      document.getElementById("edge-preset").value = "";
      for (const side of ["start", "end"]) {
        document.getElementById(`edge-${side}-fill`).checked = style[side+"Fill"] !== false;
        document.getElementById(`edge-${side}-size`).value = style[side+"Size"] ?? 10;
      }
      edgeColor.value = normalizeHex(
        style.strokeColor,
        DEFAULT_EDGE
      );
      edgeWidth.value = Math.max(
        1,
        Number(
          style.strokeWidth || 2
        )
      );
      edgeDashed.checked = Boolean(
        style.dashed
      );
    }
  }
  function applyVertexProperties() {
    const cell = graph.getSelectionCell();
    if (!cell?.isVertex()) {
      return;
    }
    graph.batchUpdate(
      () => {
        model.setValue(
          cell,
          propertyText.value
        );
        const geometry = cell.getGeometry();
        if (geometry) {
          const nextGeometry = geometry.clone();
          nextGeometry.width = Math.max(
            40,
            Number(
              propertyWidth.value
            ) || geometry.width
          );
          nextGeometry.height = Math.max(
            30,
            Number(
              propertyHeight.value
            ) || geometry.height
          );
          model.setGeometry(
            cell,
            nextGeometry
          );
        }
        const style = cell.getClonedStyle();
        style.fillColor = propertyFill.value;
        style.strokeColor = propertyStroke.value;
        style.fontColor = propertyFontColor.value;
        style.fontSize = Math.max(
          8,
          Number(
            propertyFontSize.value
          ) || 14
        );
        style.rotation = Math.max(
          0,
          Math.min(
            360,
            Number(
              propertyRotation.value
            ) || 0
          )
        );
        model.setStyle(
          cell,
          style
        );
      }
    );
  }
  function applyEdgeProperties() {
    const cell = graph.getSelectionCell();
    if (!cell?.isEdge()) {
      return;
    }
    graph.batchUpdate(
      () => {
        model.setValue(
          cell,
          edgeLabel.value
        );
        const style = cell.getClonedStyle();
        applyLineType(
          style,
          edgeStyle.value
        );
        style.startArrow = edgeStartArrow.value;
        style.endArrow = edgeEndArrow.value;
        for (const side of ["start", "end"]) {
          style[side+"Fill"] = document.getElementById(`edge-${side}-fill`).checked;
          style[side+"Size"] = Math.min(40,Math.max(4,Number(document.getElementById(`edge-${side}-size`).value)||10));
        }
        style.strokeColor = edgeColor.value;
        style.strokeWidth = Math.max(
          1,
          Number(
            edgeWidth.value
          ) || 2
        );
        style.dashed = edgeDashed.checked;
        style.fontColor = DEFAULT_TEXT;
        style.bendable = true;
        model.setStyle(
          cell,
          style
        );
      }
    );
  }
  function fitView() {
    const fitPlugin = graph.getPlugin(
      "FitPlugin"
    );
    if (fitPlugin?.fit) {
      fitPlugin.fit({
        border: 50,
        margin: 20
      });
    } else {
      graph.zoomActual();
    }
    updateZoomLabel();
  }
  function zoomAtPointer(event) {
    const rect = container.getBoundingClientRect();
    const oldScale = view.scale || 1;
    const factor = Math.exp(
      -event.deltaY * 25e-4
    );
    const newScale = clampZoom(
      oldScale * factor
    );
    if (Math.abs(
      newScale - oldScale
    ) < 1e-4) {
      return;
    }
    const localX = event.clientX - rect.left;
    const localY = event.clientY - rect.top;
    const translate = view.getTranslate();
    const worldX = localX / oldScale - translate.x;
    const worldY = localY / oldScale - translate.y;
    const nextTranslateX = localX / newScale - worldX;
    const nextTranslateY = localY / newScale - worldY;
    view.scaleAndTranslate(
      newScale,
      nextTranslateX,
      nextTranslateY
    );
    updateZoomLabel();
  }
  function panWithTrackpad(event) {
    const scale = view.scale || 1;
    const translate = view.getTranslate();
    view.setTranslate(
      translate.x - event.deltaX / scale,
      translate.y - event.deltaY / scale
    );
  }
  container.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      if (event.ctrlKey) {
        zoomAtPointer(
          event
        );
      } else {
        panWithTrackpad(
          event
        );
      }
    },
    {
      passive: false
    }
  );
  function getSvgMarkup(forPreview = false) {
    const svg = container.querySelector(
      "svg"
    );
    if (!svg) {
      return null;
    }
    const clone = svg.cloneNode(
      true
    );
    const sourceGroups = [...svg.querySelectorAll("g")];
    const clonedGroups = [...clone.querySelectorAll("g")];
    for (const pane of [view.getOverlayPane(), view.getDecoratorPane()]) {
      const index = sourceGroups.indexOf(pane);
      if (index >= 0) clonedGroups[index].remove();
    }
    clone.setAttribute(
      "xmlns",
      "http://www.w3.org/2000/svg"
    );
    if (forPreview) {
      const bounds = graph.getGraphBounds();
      const padding = 48;
      if (bounds && Number.isFinite(
        bounds.x
      ) && Number.isFinite(
        bounds.y
      ) && bounds.width > 0 && bounds.height > 0) {
        const x = bounds.x - padding;
        const y = bounds.y - padding;
        const width = bounds.width + padding * 2;
        const height = bounds.height + padding * 2;
        clone.setAttribute(
          "viewBox",
          `${x} ${y} ${width} ${height}`
        );
        clone.setAttribute(
          "width",
          String(
            width
          )
        );
        clone.setAttribute(
          "height",
          String(
            height
          )
        );
        clone.setAttribute(
          "preserveAspectRatio",
          "xMidYMid meet"
        );
      }
      clone.style.background = "transparent";
    }
    clone.style.background = document.documentElement.dataset.theme === "dark" ? "#141820" : "#ffffff";
    const attributions = [...new Set((diagramData.elements || []).map(e=>e.attribution).filter(Boolean))];
    if (attributions.length) {
      const desc = document.createElementNS("http://www.w3.org/2000/svg", "desc");
      desc.textContent = attributions.join("; "); clone.prepend(desc);
    }
    return new XMLSerializer().serializeToString(
      clone
    );
  }
  function refreshPreview() {
    const markup = getSvgMarkup(
      true
    );
    if (!markup) {
      previewImage.removeAttribute(
        "src"
      );
      previewImage.alt = "Diagram preview unavailable";
      return;
    }
    if (previewObjectUrl) {
      URL.revokeObjectURL(
        previewObjectUrl
      );
    }
    const blob = new Blob(
      [
        markup
      ],
      {
        type: "image/svg+xml"
      }
    );
    previewObjectUrl = URL.createObjectURL(
      blob
    );
    previewImage.src = previewObjectUrl;
    previewImage.alt = "Diagram preview";
  }
  const editToggle = document.getElementById("edit-diagram");
  let editing = false;
  let changingView = false;
  let ownedFullscreen = false;
  function updateEditToggle() {
    editToggle.setAttribute("aria-expanded", String(editing));
    editToggle.setAttribute("aria-label", editing ? "Collapse to diagram preview" : "Expand diagram to edit");
    editToggle.title = editing ? "تصغير والعودة إلى المعاينة" : "تكبير الرسم وتعديله";
    editToggle.querySelector("path").setAttribute("d", editing
      ? "M3 8h5V3m8 0v5h5M3 16h5v5m8 0v-5h5M3 3l5 5m13-5-5 5M3 21l5-5m13 5-5-5"
      : "M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M3 3l6 6m12-6-6 6M3 21l6-6m12 6-6-6");
  }
  updateEditToggle();
  async function showEditor() {
    if (editing || changingView) return;
    changingView = true;
    editing = true;
    updateEditToggle();
    previewView.hidden = true;
    editorView.classList.remove(
      "editor-view--preparing"
    );
    try {
      if (!document.fullscreenElement && shell.requestFullscreen) {
        await shell.requestFullscreen();
      }
    } catch (error) {
      console.warn(
        "Fullscreen could not start automatically.",
        error
      );
    } finally {
      changingView = false;
    }
    requestAnimationFrame(
      () => {
        if (!editing) return;
        graph.refresh?.();
        fitView();
        reportHeight();
      }
    );
  }
  async function showPreview() {
    if (!editing || changingView) return;
    changingView = true;
    try {
    graph.stopEditing?.(false);
    graph.clearSelection?.();
    graph.refresh?.();
    fitView();
    refreshPreview();
    editing = false;
    updateEditToggle();
    editorView.classList.add(
      "editor-view--preparing"
    );
    previewView.hidden = false;
    if (document.fullscreenElement === shell) {
      try {
        await document.exitFullscreen();
      } catch (error) {
        console.warn(
          "Fullscreen could not close.",
          error
        );
      }
    }
    reportHeight();
    } finally {
      changingView = false;
    }
  }
  function exportSvg() {
    const markup = getSvgMarkup(true);
    if (!markup) {
      return;
    }
    const blob = new Blob(
      [
        markup
      ],
      {
        type: "image/svg+xml"
      }
    );
    const url = URL.createObjectURL(
      blob
    );
    const link = document.createElement(
      "a"
    );
    link.href = url;
    link.download = "diagram.svg";
    link.click();
    URL.revokeObjectURL(
      url
    );
  }
  function exportPng() {
    const markup = getSvgMarkup(true);
    if (!markup) {
      return;
    }
    const blob = new Blob(
      [
        markup
      ],
      {
        type: "image/svg+xml"
      }
    );
    const url = URL.createObjectURL(
      blob
    );
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement(
        "canvas"
      );
      canvas.width = Math.max(
        1,
        image.width * 2
      );
      canvas.height = Math.max(
        1,
        image.height * 2
      );
      const context = canvas.getContext(
        "2d"
      );
      context.scale(
        2,
        2
      );
      context.drawImage(
        image,
        0,
        0
      );
      const link = document.createElement(
        "a"
      );
      link.href = canvas.toDataURL(
        "image/png"
      );
      link.download = "diagram.png";
      link.click();
      URL.revokeObjectURL(
        url
      );
    };
    image.onerror = () => {
      URL.revokeObjectURL(
        url
      );
    };
    image.src = url;
  }
  function shapePreview(type) {
    const paths = {
      boundary: '<rect x="3" y="3" width="42" height="30"/><path d="M3 11h42"/>',
      actor: '<circle cx="24" cy="6" r="4"/><path d="M24 10v12M14 15h20M24 22l-9 11m9-11 9 11"/>',
      data: '<path d="M12 5h33l-9 26H3z"/>',
      document: '<path d="M5 4h38v23c-14-8-24 11-38 0z"/>',
      subprocess: '<rect x="4" y="5" width="40" height="26"/><path d="M10 5v26m28-26v26"/>',
      class: '<rect x="4" y="2" width="40" height="32"/><path d="M4 12h40M4 23h40M9 17h18M9 28h22"/>',
      table: '<rect x="4" y="2" width="40" height="32"/><path d="M4 12h40M4 23h40M16 12v22"/>',
      note: '<path d="M5 3h28l10 10v20H5zM33 3v10h10"/>',
      package: '<path d="M4 10V3h18v7h22v23H4zM4 10h18"/>',
      lifeline: '<rect x="10" y="2" width="28" height="10"/><path stroke-dasharray="3 2" d="M24 12v23"/>',
      diamond: '<path d="M24 2l21 16-21 16L3 18z"/>',
      triangle: '<path d="M24 3l21 29H3z"/>',
      hexagon: '<path d="M12 4h24l10 14-10 14H12L2 18z"/>',
      ellipse: '<ellipse cx="24" cy="18" rx="21" ry="14"/>',
      double_ellipse: '<ellipse cx="24" cy="18" rx="21" ry="14"/><ellipse cx="24" cy="18" rx="17" ry="10"/>',
      circle: '<circle cx="24" cy="18" r="15"/>',
      rounded_rectangle: '<rect x="3" y="5" width="42" height="26" rx="7"/>',
      rectangle: '<rect x="3" y="5" width="42" height="26"/>',
      swimlane: '<rect x="3" y="3" width="42" height="30"/><path d="M3 11h42M3 19h42M3 26h42M14 11v22"/>',
      pool: '<rect x="3" y="3" width="42" height="30"/><path d="M10 3v30M20 3v30M10 13h35M10 23h35"/>',
      text: '<path d="M12 5h24M24 5v26M18 31h12"/>',
      initial_state: '<circle cx="24" cy="18" r="12" fill="currentColor"/>',
      final_state: '<circle cx="24" cy="18" r="15"/><circle cx="24" cy="18" r="10" fill="currentColor"/>',
      fork_join: '<rect x="3" y="15" width="42" height="6" fill="currentColor"/>',
      activation: '<rect x="19" y="2" width="10" height="32"/>',
      bpmn_start_event: '<circle cx="24" cy="18" r="14"/>',
      bpmn_intermediate_event: '<circle cx="24" cy="18" r="15"/><circle cx="24" cy="18" r="11"/>',
      bpmn_end_event: '<circle cx="24" cy="18" r="14" stroke-width="4"/>'
    };
    const aliases = {
      entity: "table",
      process: "rectangle",
      decision: "diamond",
      use_case: "ellipse",
      start_end: "rounded_rectangle",
      bpmn_task: "rounded_rectangle",
      container: "boundary",
      system_boundary: "boundary"
    };
    let drawing = paths[aliases[type] || type];
    if (type.endsWith("_gateway")) {
      drawing = paths.diamond + (type.includes("exclusive") ? '<path d="M19 13l10 10m0-10L19 23"/>' : type.includes("parallel") ? '<path d="M17 18h14m-7-7v14"/>' : '<circle cx="24" cy="18" r="6"/>');
    }
    if (type === "bpmn_subprocess") drawing = paths.rounded_rectangle + '<rect x="20" y="21" width="8" height="8"/><path d="M22 25h4m-2-2v4"/>';
    if (!drawing) return window.CanvasDiagramMaxGraph.getIconSvg(type, "currentColor") || "";
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 36" width="48" height="36" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round">' + drawing + "</svg>";
  }
  const shapeCategories = [["General", [["rectangle", "Rectangle", 160, 80], ["rounded_rectangle", "Rounded", 160, 80], ["circle", "Circle", 100, 100], ["ellipse", "Ellipse", 160, 90], ["double_ellipse", "Double ellipse", 160, 100], ["diamond", "Diamond", 120, 100], ["triangle", "Triangle", 120, 100], ["hexagon", "Hexagon", 150, 90], ["text", "Text", 160, 40], ["note", "Note", 160, 100]]], ["Flowchart", [["start_end", "Start / End", 150, 60], ["process", "Process", 160, 80], ["decision", "Decision", 140, 100], ["data", "Input / Output", 160, 80], ["document", "Document", 160, 90], ["subprocess", "Predefined process", 180, 80]]], ["UML Use Case", [["actor", "Actor", 65, 100], ["use_case", "Use case", 160, 80], ["system_boundary", "System boundary", 400, 280], ["note", "Note", 160, 100]]], ["Business Process (BPMN)", [["bpmn_start_event", "Start event", 50, 50], ["bpmn_intermediate_event", "Intermediate event", 50, 50], ["bpmn_end_event", "End event", 50, 50], ["bpmn_task", "Task", 160, 80], ["bpmn_subprocess", "Collapsed subprocess", 180, 90], ["bpmn_exclusive_gateway", "Exclusive gateway", 70, 70], ["bpmn_parallel_gateway", "Parallel gateway", 70, 70], ["bpmn_inclusive_gateway", "Inclusive gateway", 70, 70], ["pool", "Pool", 480, 240], ["swimlane", "Swimlanes", 520, 260]]], ["UML Class", [["class", "Class", 230, 150], ["package", "Package", 250, 180], ["note", "Note", 160, 100]]], ["Entity Relationship (ERD)", [["entity", "Entity", 210, 130], ["table", "Table", 210, 150], ["database", "Database", 120, 140]]], ["UML Activity / State", [["initial_state", "Initial state", 35, 35], ["final_state", "Final state", 45, 45], ["bpmn_task", "Activity", 150, 70], ["decision", "Decision / Merge", 80, 80], ["fork_join", "Fork / Join", 220, 12], ["swimlane", "Swimlane", 520, 260]]], ["UML Sequence", [["actor", "Actor", 65, 100], ["lifeline", "Lifeline", 140, 240], ["activation", "Activation", 24, 110], ["note", "Note", 160, 100]]], ["Architecture / Network", [["user", "User", 150, 70], ["server", "Server", 160, 80], ["database", "Database", 120, 140], ["cloud", "Cloud", 170, 100], ["api", "API", 150, 70], ["service", "Service", 160, 80], ["queue", "Queue", 160, 80], ["container", "Container", 300, 220], ["code", "Code", 160, 80]]], ["Containers", [["swimlane", "Swimlane", 520, 260], ["pool", "Pool", 480, 240], ["system_boundary", "System boundary", 400, 280], ["package", "Package", 250, 180]]]];
  const defaults = {
    class: "Class\n+ attribute: Type\n---\n+ method(): Type",
    table: "Table\nPK  id: integer\nFK  owner_id: integer\nname: varchar",
    entity: "Entity\nPK  id\nattribute",
    initial_state: "",
    final_state: "",
    fork_join: "",
    activation: ""
  };
  const libraryRoot = document.getElementById("shape-libraries");
  for (const [category, entries] of shapeCategories) {
    const section = document.createElement("details");
    section.className = "shape-section";
    section.dataset.shapeSection = "";
    section.dataset.category = category.toLowerCase();
    section.open = category === "General";
    const summary = document.createElement("summary");
    summary.textContent = category;
    section.append(summary);
    const grid = document.createElement("div");
    grid.className = "shape-grid";
    for (const [type, label, width, height] of entries) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "shape-button";
      button.dataset.type = type;
      button.title = "Add " + label;
      const symbol = document.createElement("span");
      symbol.className = "shape-symbol";
      symbol.setAttribute("aria-hidden", "true");
      symbol.innerHTML = shapePreview(type);
      const name = document.createElement("span");
      name.className = "shape-name";
      name.textContent = label;
      button.append(symbol, name);
      button.addEventListener("click", () => addElement(type, defaults[type] ?? label, width, height));
      grid.append(button);
    }
    section.append(grid);
    libraryRoot.append(section);
  }
  let openBeforeSearch = null;
  shapeSearch.addEventListener("input", () => {
    const query = shapeSearch.value.trim().toLowerCase();
    const sections = [...libraryRoot.querySelectorAll("details")];
    if (query && !openBeforeSearch) openBeforeSearch = sections.map((s) => s.open);
    let total = 0;
    sections.forEach((section, index) => {
      let count = 0;
      section.querySelectorAll(".shape-button").forEach((button) => {
        const match = !query || (section.dataset.category + " " + button.textContent + " " + button.dataset.type).toLowerCase().includes(query);
        button.hidden = !match;
        if (match) count++;
      });
      section.hidden = count === 0;
      total += count;
      if (query) section.open = count > 0;
      else if (openBeforeSearch) section.open = openBeforeSearch[index];
    });
    if (!query) openBeforeSearch = null;
    document.getElementById("shape-empty").hidden = total > 0;
  });
  document.getElementById(
    "edit-diagram"
  ).addEventListener(
    "click",
    () => { if (editing) void showPreview(); else void showEditor(); }
  );
  undoButton.addEventListener(
    "click",
    () => {
      if (undoManager.canUndo()) {
        undoManager.undo();
        syncProperties();
        updateUndoButtons();
      }
    }
  );
  redoButton.addEventListener(
    "click",
    () => {
      if (undoManager.canRedo()) {
        undoManager.redo();
        syncProperties();
        updateUndoButtons();
      }
    }
  );
  duplicateButton.addEventListener(
    "click",
    duplicateSelected
  );
  deleteButton.addEventListener(
    "click",
    deleteSelected
  );
  document.getElementById(
    "layout-horizontal"
  ).addEventListener(
    "click",
    () => applyAutomaticLayout(
      "horizontal"
    )
  );
  document.getElementById(
    "layout-vertical"
  ).addEventListener(
    "click",
    () => applyAutomaticLayout(
      "vertical"
    )
  );
  document.getElementById(
    "zoom-in"
  ).addEventListener(
    "click",
    () => {
      graph.zoomIn();
      updateZoomLabel();
    }
  );
  document.getElementById(
    "zoom-out"
  ).addEventListener(
    "click",
    () => {
      graph.zoomOut();
      updateZoomLabel();
    }
  );
  document.getElementById(
    "fit-view"
  ).addEventListener(
    "click",
    fitView
  );
  document.getElementById(
    "export-svg"
  ).addEventListener(
    "click",
    exportSvg
  );
  document.getElementById(
    "export-png"
  ).addEventListener(
    "click",
    exportPng
  );
  document.addEventListener(
    "fullscreenchange",
    () => {
      if (document.fullscreenElement === shell) {
        ownedFullscreen = true;
        requestAnimationFrame(() => { if (editing) { graph.refresh?.(); fitView(); } });
      } else if (ownedFullscreen) {
        ownedFullscreen = false;
        if (editing && !changingView) void showPreview();
      }
    }
  );
  document.addEventListener("keydown", (event) => {
    // Fallback when the iframe sandbox does not permit native fullscreen.
    if (event.key === "Escape" && editing && !document.fullscreenElement && !graph.isEditing?.()) {
      event.preventDefault();
      void showPreview();
    }
  });
  graph.getSelectionModel().addListener(
    "change",
    syncProperties
  );
  model.addListener(
    "change",
    () => {
      updateUndoButtons();
      syncProperties();
    }
  );
  [
    propertyText,
    propertyWidth,
    propertyHeight,
    propertyRotation,
    propertyFill,
    propertyStroke,
    propertyFontColor,
    propertyFontSize
  ].forEach(
    (input) => {
      input.addEventListener(
        "change",
        () => {
          applyVertexProperties();
          syncProperties();
        }
      );
    }
  );
  [
    edgeLabel,
    edgeStyle,
    edgeStartArrow,
    edgeEndArrow,
    edgeColor,
    edgeWidth,
    edgeDashed
  ].forEach(
    (input) => {
      input.addEventListener(
        "change",
        () => {
          applyEdgeProperties();
          syncProperties();
        }
      );
    }
  );
  window.addEventListener(
    "keydown",
    (event) => {
      const editingField = [
        "INPUT",
        "TEXTAREA",
        "SELECT"
      ].includes(
        document.activeElement?.tagName
      );
      const modifier = event.ctrlKey || event.metaKey;
      if (modifier && !editingField) {
        const key = event.key.toLowerCase();
        if (key === "z") {
          event.preventDefault();
          if (event.shiftKey) {
            if (undoManager.canRedo()) {
              undoManager.redo();
            }
          } else if (undoManager.canUndo()) {
            undoManager.undo();
          }
          syncProperties();
          updateUndoButtons();
          return;
        }
        if (key === "y") {
          event.preventDefault();
          if (undoManager.canRedo()) {
            undoManager.redo();
          }
          syncProperties();
          updateUndoButtons();
          return;
        }
        if (key === "d") {
          event.preventDefault();
          duplicateSelected();
          return;
        }
      }
      if ((event.key === "Delete" || event.key === "Backspace") && !editingField) {
        deleteSelected();
      }
    }
  );
  for (const id of ["edge-start-fill","edge-end-fill","edge-start-size","edge-end-size"]) document.getElementById(id).addEventListener("change",applyEdgeProperties);
  document.getElementById("edge-preset").addEventListener("change", event => {
    const presets = {
      association:["none","none",false,true,true], dependency:["none","open",true,true,false],
      inheritance:["none","block",false,true,false], realization:["none","block",true,true,false],
      aggregation:["diamond","none",false,false,true], composition:["diamond","none",false,true,true],
      sequence:["none","block",false,true,true], message:["oval","open",true,false,false],
      oneMany:["erOne","erMany",false,false,false], manyMany:["erMany","erMany",false,false,false],
      bidirectional:["classic","classic",false,true,true]
    };
    const p = presets[event.target.value]; if (!p) return;
    edgeStartArrow.value=p[0]; edgeEndArrow.value=p[1]; edgeDashed.checked=p[2];
    document.getElementById("edge-start-fill").checked=p[3]; document.getElementById("edge-end-fill").checked=p[4];
    applyEdgeProperties();
  });
  // Backend document renderer consumes the exact same SVG as browser export.
  window.CanvasDiagramExport = { svg: () => getSvgMarkup(true) };
  function reportHeight() {
    parent.postMessage(
      {
        type: "iframe:height",
        height: document.documentElement.scrollHeight
      },
      "*"
    );
  }
  new ResizeObserver(
    () => {
      graph.refresh?.();
      reportHeight();
    }
  ).observe(
    stage
  );
  new ResizeObserver(
    reportHeight
  ).observe(
    document.body
  );
  const credits = [...new Set((diagramData.elements || []).map(e=>e.attribution).filter(Boolean))];
  if (credits.length) { const box=document.getElementById("icon-credits");box.hidden=false;box.textContent=credits.join(" · "); }
  
function detectDiagramType() {

    const types = new Set(
        (diagramData.elements || []).map(
            element => element.type
        )
    );

    const hasAny = values =>
        values.some(
            value => types.has(value)
        );

    if (hasAny([
        'entity',
        'table'
    ])) {
        return 'erd';
    }

    if (hasAny([
        'class',
        'actor',
        'use_case',
        'interface',
        'package'
    ])) {
        return 'uml';
    }

    if (hasAny([
        'start_end',
        'process',
        'decision',
        'document',
        'data',
        'subprocess'
    ])) {
        return 'flowchart';
    }

    if (hasAny([
        'user',
        'server',
        'database',
        'cloud',
        'api',
        'service',
        'queue',
        'container',
        'code',
        'icon'
    ])) {
        return 'architecture';
    }

    return 'general';
}


function autoArrangeInitialDiagram() {

    const elements =
        diagramData.elements || [];

    if (elements.length < 2) {
        return;
    }

    const type =
        detectDiagramType();

    let direction =
        'horizontal';

    if (type === 'flowchart') {
        direction = 'vertical';
    }

    if (
        type === 'architecture'
        || type === 'uml'
        || type === 'erd'
    ) {
        direction = 'horizontal';
    }

    try {

        engine.applyAutoLayout(
            graph,
            direction
        );

        graph.refresh?.();

        setStatus(
            `Auto-arranged ${type} diagram (${direction}).`
        );

    } catch (error) {

        console.warn(
            'Automatic diagram layout failed',
            error
        );
    }
}


loadDiagram();

autoArrangeInitialDiagram();
  updateZoomLabel();
  syncProperties();
  updateUndoButtons();
  requestAnimationFrame(
    () => {
      graph.clearSelection?.();
      fitView();
      requestAnimationFrame(
        () => {
          refreshPreview();
          reportHeight();
        }
      );
    }
  );
  setStatus(
    "Editor ready. Drag empty space to pan, use two fingers to move, pinch to zoom, and drag line handles to reshape connections."
  );
})();
</script>
</body>
</html>"""
    return (template.replace("__TITLE__", title)
            .replace("__GRAPH_B64__", graph_b64)
            .replace("__MAXGRAPH_URL__", maxgraph_url))
