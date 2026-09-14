import {
  ShapeRegistry,
  EdgeMarkerRegistry,
  Shape,
  ConnectionConstraint,
  Graph,
  HierarchicalLayout,
  ImageBox,
  InternalEvent,
  Point,
  UndoManager
} from "@maxgraph/core";
import {
  icons as lucideIcons
} from "@iconify-json/lucide";
import {
  getIconData
} from "@iconify/utils";
const BUNDLE_VERSION = "8";

class DiagramNotationShape extends Shape {
  paintVertexShape(c, x, y, w, h) {
    c.translate(x, y);
    const kind = this.style.diagramType;
    const line = (points) => {
      c.begin();
      c.moveTo(...points[0]);
      points.slice(1).forEach((p) => c.lineTo(...p));
      c.stroke();
    };
    const box = () => {
      c.rect(0, 0, w, h);
      c.fillAndStroke();
    };
    if (["pool", "swimlane"].includes(kind)) {
      box();
      let names;
      try { names = JSON.parse(this.style.laneLabels || "[]"); } catch (_) { names = []; }
      if (!Array.isArray(names) || !names.length) names = ["Lane 1", "Lane 2", "Lane 3"];
      const verticalTitle = kind === "pool";
      const titleWidth = verticalTitle ? 32 : 0;
      const top = verticalTitle ? 0 : 32;
      const labelWidth = Math.min(110, Math.max(60, w * .22));
      const dividerX = titleWidth + labelWidth;
      const rowHeight = (h - top) / names.length;
      c.setFontColor(this.style.fontColor || "#000000");
      c.setFontSize(Number(this.style.fontSize || 14));
      c.setFontStyle(1);
      if (verticalTitle) {
        line([[titleWidth,0],[titleWidth,h]]);
        c.text(titleWidth/2,h/2,h-12,titleWidth,String(this.state.cell.value || "Pool"),
          "center","middle",false,"","hidden",true,-90);
      } else {
        line([[0,top],[w,top]]);
        c.text(w/2,top/2,w-16,top,String(this.state.cell.value || "Swimlane"),
          "center","middle",false,"","hidden",true);
      }
      c.setFontStyle(0);
      line([[dividerX,top],[dividerX,h]]);
      names.forEach((name, index) => {
        const y = top + index * rowHeight;
        if (index) line([[titleWidth,y],[w,y]]);
        c.text(titleWidth + labelWidth/2,y + rowHeight/2,labelWidth-12,rowHeight-8,
          String(name),"center","middle",false,"","hidden",true);
      });
    } else if (kind === "actor") {
      const head = Math.min(w * 0.3, h * 0.24);
      c.ellipse((w - head) / 2, 0, head, head);
      c.fillAndStroke();
      line([[w / 2, head], [w / 2, h * 0.65]]);
      line([[w * 0.12, h * 0.4], [w * 0.88, h * 0.4]]);
      line([[w * 0.15, h], [w / 2, h * 0.65], [w * 0.85, h]]);
    } else if (kind === "data") {
      c.begin();
      c.moveTo(w * 0.18, 0);
      c.lineTo(w, 0);
      c.lineTo(w * 0.82, h);
      c.lineTo(0, h);
      c.close();
      c.fillAndStroke();
    } else if (kind === "document") {
      c.begin();
      c.moveTo(0, 0);
      c.lineTo(w, 0);
      c.lineTo(w, h * 0.82);
      c.curveTo(w * 0.65, h * 0.55, w * 0.35, h * 1.05, 0, h * 0.82);
      c.close();
      c.fillAndStroke();
    } else if (kind === "subprocess") {
      box();
      line([[w * 0.12, 0], [w * 0.12, h]]);
      line([[w * 0.88, 0], [w * 0.88, h]]);
    } else if (["class", "entity", "table"].includes(kind)) {
      box();
      const rows = String(this.state.cell.value || "").split("\n");
      if (kind === "class" && !rows.some(row => row.trim() === "---")) {
        const operation = rows.findIndex((row,index) => index > 0 && row.includes("("));
        if (operation > 0) rows.splice(operation,0,"---");
        else { if (rows.length === 1) rows.push(""); rows.push("---",""); }
      }
      const size = Number(this.style.fontSize || 14);
      const header = Math.max(30, size + 16);
      const step = Math.max(20, size * 1.5);
      c.setFontColor(this.style.fontColor || "#000000");
      c.setFontSize(size);
      c.setFontStyle(1);
      c.text(w / 2, header / 2, w - 16, header, rows[0] || "", "center", "middle", false, "", "hidden", true);
      line([[0, header], [w, header]]);
      c.setFontStyle(0);
      let top = header;
      for (const row of rows.slice(1)) {
        if (row.trim() === "---") {
          line([[0, top], [w, top]]);
          continue;
        }
        if (top + step > h) break;
        c.text(8, top + step / 2, w - 16, step, row, "left", "middle", false, "", "hidden", true);
        top += step;
      }
    } else if (kind === "note") {
      const fold = Math.min(20, w * 0.2, h * 0.2);
      c.begin();
      c.moveTo(0, 0);
      c.lineTo(w - fold, 0);
      c.lineTo(w, fold);
      c.lineTo(w, h);
      c.lineTo(0, h);
      c.close();
      c.fillAndStroke();
      line([[w - fold, 0], [w - fold, fold], [w, fold]]);
    } else if (kind === "package") {
      c.begin();
      c.moveTo(0, h * 0.2);
      c.lineTo(0, 0);
      c.lineTo(w * 0.45, 0);
      c.lineTo(w * 0.45, h * 0.2);
      c.lineTo(w, h * 0.2);
      c.lineTo(w, h);
      c.lineTo(0, h);
      c.close();
      c.fillAndStroke();
      line([[0, h * 0.2], [w * 0.45, h * 0.2]]);
    } else if (kind === "lifeline") {
      c.rect(0, 0, w, Math.min(40, h * 0.3));
      c.fillAndStroke();
      c.setDashed(true);
      line([[w / 2, Math.min(40, h * 0.3)], [w / 2, h]]);
    } else if (kind.startsWith("bpmn_") && kind.endsWith("event")) {
      if (kind === "bpmn_end_event") c.setStrokeWidth(4);
      c.ellipse(0, 0, w, h);
      c.fillAndStroke();
      if (kind === "bpmn_intermediate_event") {
        c.ellipse(5, 5, w - 10, h - 10);
        c.stroke();
      }
    } else if (kind.startsWith("bpmn_") && kind.endsWith("gateway")) {
      c.begin();
      c.moveTo(w / 2, 0);
      c.lineTo(w, h / 2);
      c.lineTo(w / 2, h);
      c.lineTo(0, h / 2);
      c.close();
      c.fillAndStroke();
      if (kind === "bpmn_exclusive_gateway") {
        line([[w * 0.35, h * 0.35], [w * 0.65, h * 0.65]]);
        line([[w * 0.65, h * 0.35], [w * 0.35, h * 0.65]]);
      } else if (kind === "bpmn_parallel_gateway") {
        line([[w * 0.3, h / 2], [w * 0.7, h / 2]]);
        line([[w / 2, h * 0.3], [w / 2, h * 0.7]]);
      } else {
        c.ellipse(w * 0.32, h * 0.32, w * 0.36, h * 0.36);
        c.stroke();
      }
    } else if (kind === "bpmn_subprocess") {
      c.roundrect(0, 0, w, h, 10, 10);
      c.fillAndStroke();
      c.rect(w / 2 - 7, h - 18, 14, 14);
      c.stroke();
      line([[w / 2 - 4, h - 11], [w / 2 + 4, h - 11]]);
      line([[w / 2, h - 15], [w / 2, h - 7]]);
    } else if (kind === "final_state") {
      c.ellipse(0, 0, w, h);
      c.fillAndStroke();
      c.setFillColor(this.style.strokeColor || "#334155");
      c.ellipse(w * 0.2, h * 0.2, w * 0.6, h * 0.6);
      c.fill();
    } else {
      box();
    }
  }
}
ShapeRegistry.add("diagramNotation", DiagramNotationShape);
const ICON_MAP = {
  user: "user",
  actor: "user-round",
  server: "server",
  database: "database",
  cloud: "cloud",
  api: "braces",
  service: "boxes",
  queue: "layers-3",
  container: "box",
  code: "code-2",
  document: "file-text",
  network: "network"
};
function getIconSvg(name, color = "#334155") {
  const iconName = ICON_MAP[name] || name;
  const icon = getIconData(
    lucideIcons,
    iconName
  );
  if (!icon) {
    const fallback = {
      user: '<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3"/>',
      server: '<rect x="3" y="3" width="18" height="7" rx="2"/><rect x="3" y="14" width="18" height="7" rx="2"/><path d="M6 6h1m-1 11h1"/>',
      database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 4 18 4 18 0V5M3 12c0 4 18 4 18 0"/>',
      cloud: '<path d="M6 19a5 5 0 0 1-1-10 7 7 0 0 1 13-2 6 6 0 0 1 0 12z"/>',
      api: '<path d="M9 3H7v7l-3 2 3 2v7h2m6-18h2v7l3 2-3 2v7h-2"/>',
      service: '<rect x="2" y="2" width="8" height="8"/><rect x="14" y="2" width="8" height="8"/><rect x="8" y="14" width="8" height="8"/>',
      queue: '<path d="M3 5h18M3 12h18M3 19h18"/>',
      code: '<path d="m8 5-6 7 6 7m8-14 6 7-6 7M14 3l-4 18"/>',
    };
    const body = fallback[name];
    return body ? `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${body}</svg>` : null;
  }
  const width = icon.width || 24;
  const height = icon.height || 24;
  const body = String(
    icon.body || ""
  ).replaceAll(
    "currentColor",
    color
  );
  return `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="32"
      height="32"
      viewBox="0 0 ${width} ${height}"
      aria-hidden="true"
    >
      ${body}
    </svg>
  `.trim();
}
function getIconDataUri(name, color = "#334155") {
  const svg = getIconSvg(
    name,
    color
  );
  return svg ? "data:image/svg+xml," + encodeURIComponent(
    svg
  ) : null;
}
const portSvg = "data:image/svg+xml," + encodeURIComponent(`
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="18"
      height="18"
      viewBox="0 0 18 18"
    >
      <circle
        cx="9"
        cy="9"
        r="7"
        fill="#2563eb"
        stroke="#ffffff"
        stroke-width="2"
      />
    </svg>
  `);
function configurePorts(graph) {
  graph.getAllConnectionConstraints = (terminal) => {
    if (!terminal?.cell?.isVertex()) {
      return null;
    }
    return [
      new ConnectionConstraint(
        new Point(
          0.5,
          0
        ),
        true
      ),
      new ConnectionConstraint(
        new Point(
          1,
          0
        ),
        true
      ),
      new ConnectionConstraint(
        new Point(
          1,
          0.5
        ),
        true
      ),
      new ConnectionConstraint(
        new Point(
          1,
          1
        ),
        true
      ),
      new ConnectionConstraint(
        new Point(
          0.5,
          1
        ),
        true
      ),
      new ConnectionConstraint(
        new Point(
          0,
          1
        ),
        true
      ),
      new ConnectionConstraint(
        new Point(
          0,
          0.5
        ),
        true
      ),
      new ConnectionConstraint(
        new Point(
          0,
          0
        ),
        true
      )
    ];
  };
  const connectionHandler = graph.getPlugin(
    "ConnectionHandler"
  );
  if (!connectionHandler?.constraintHandler) {
    return;
  }
  connectionHandler.constraintHandler.pointImage = new ImageBox(
    portSvg,
    18,
    18
  );
  connectionHandler.constraintHandler.highlightColor = "#2563eb";
  connectionHandler.outlineConnect = true;
  connectionHandler.cursorConnect = "crosshair";
  connectionHandler.select = true;
}
function configurePanning(graph) {
  graph.setPanning(
    true
  );
  const panningHandler = graph.getPlugin(
    "PanningHandler"
  );
  if (!panningHandler) {
    return;
  }
  if (typeof panningHandler.setPanningEnabled === "function") {
    panningHandler.setPanningEnabled(
      true
    );
  }
  if (typeof panningHandler.setPinchEnabled === "function") {
    panningHandler.setPinchEnabled(
      true
    );
  }
  panningHandler.useLeftButtonForPanning = true;
  panningHandler.ignoreCell = false;
  panningHandler.useGrid = false;
}
function createGraph(container) {
  if (!container) {
    throw new Error(
      "Graph container was not found"
    );
  }
  InternalEvent.disableContextMenu(
    container
  );
  const graph = new Graph(
    container
  );
  const nativeGetLabel = graph.getLabel.bind(graph);
  graph.getLabel = (cell) => ["class", "entity", "table", "pool", "swimlane"].includes(cell?.style?.diagramType) ? "" : nativeGetLabel(cell);
  graph.getEditingValue = (cell) => String(cell.value ?? "");
  graph.setConnectable(
    true
  );
  graph.setCellsEditable(
    true
  );
  graph.setCellsMovable(
    true
  );
  graph.setCellsResizable(
    true
  );
  graph.setCellsSelectable(
    true
  );
  graph.setCellsBendable(
    true
  );
  graph.setCellsDisconnectable(
    true
  );
  graph.setCellsCloneable(
    true
  );
  const defaultEdgeStyle = graph.getStylesheet().getDefaultEdgeStyle();
  defaultEdgeStyle.edgeStyle = "orthogonalEdgeStyle";
  defaultEdgeStyle.endArrow = "classic";
  defaultEdgeStyle.startArrow = "none";
  defaultEdgeStyle.strokeColor = "#475569";
  defaultEdgeStyle.strokeWidth = 2;
  defaultEdgeStyle.fontColor = "#000000";
  defaultEdgeStyle.bendable = true;
  defaultEdgeStyle.rounded = true;
  graph.centerZoom = false;
  configurePorts(
    graph
  );
  configurePanning(
    graph
  );
  return graph;
}
function createUndoManager(graph) {
  const undoManager = new UndoManager(
    200
  );
  const listener = (_sender, event) => {
    const edit = event.getProperty(
      "edit"
    );
    if (edit) {
      undoManager.undoableEditHappened(
        edit
      );
    }
  };
  graph.getDataModel().addListener(
    InternalEvent.UNDO,
    listener
  );
  graph.getView().addListener(
    InternalEvent.UNDO,
    listener
  );
  return undoManager;
}
function applyAutoLayout(graph, direction = "horizontal") {
  const parent = graph.getDefaultParent();
  const orientation = direction === "vertical" ? "north" : "west";
  const layout = new HierarchicalLayout(
    graph,
    orientation,
    true
  );
  layout.intraCellSpacing = 60;
  layout.interRankCellSpacing = 100;
  layout.parallelEdgeSpacing = 28;
  layout.interHierarchySpacing = 90;
  graph.batchUpdate(
    () => {
      layout.execute(
        parent
      );
    }
  );
}
function createTestDiagram(container) {
  const graph = createGraph(
    container
  );
  graph.batchUpdate(
    () => {
      const user = graph.insertVertex({
        value: "User",
        position: [
          40,
          80
        ],
        size: [
          110,
          60
        ],
        style: {
          rounded: true,
          fillColor: "#ffffff",
          fontColor: "#000000",
          strokeColor: "#334155"
        }
      });
      const webui = graph.insertVertex({
        value: "Open WebUI",
        position: [
          240,
          80
        ],
        size: [
          150,
          60
        ],
        style: {
          rounded: true,
          fillColor: "#ffffff",
          fontColor: "#000000",
          strokeColor: "#334155"
        }
      });
      const api = graph.insertVertex({
        value: "Workbench API",
        position: [
          500,
          80
        ],
        size: [
          170,
          60
        ],
        style: {
          fillColor: "#ffffff",
          fontColor: "#000000",
          strokeColor: "#334155"
        }
      });
      graph.insertEdge({
        source: user,
        target: webui,
        style: {
          edgeStyle: "orthogonalEdgeStyle",
          endArrow: "classic",
          strokeColor: "#475569",
          bendable: true
        }
      });
      graph.insertEdge({
        source: webui,
        target: api,
        style: {
          edgeStyle: "orthogonalEdgeStyle",
          endArrow: "classic",
          strokeColor: "#475569",
          bendable: true
        }
      });
    }
  );
  return graph;
}
export {
  BUNDLE_VERSION,
  applyAutoLayout,
  createGraph,
  createTestDiagram,
  createUndoManager,
  getIconDataUri,
  getIconSvg
};

// Crow's-foot cardinalities, drawn in endpoint-local coordinates for any direction.
for (const kind of ["erOne","erMany","erZeroOne","erOneMany","erZeroMany"]) {
  EdgeMarkerRegistry.add(kind, (c,shape,type,pe,ux,uy,size,source,sw) => {
    const tip=pe.clone(), unit=Math.max(6,size), many=kind.includes("Many")||kind==="erMany";
    const zero=kind.includes("Zero"), one=kind==="erOne"||kind==="erOneMany";
    pe.x-=ux*(zero?unit*2:unit); pe.y-=uy*(zero?unit*2:unit);
    return () => {
      const point=(d,q)=>[tip.x-ux*d-uy*q,tip.y-uy*d+ux*q];
      const line=(a,b)=>{ c.begin();c.moveTo(...point(...a));c.lineTo(...point(...b));c.stroke(); };
      if(many) for(const q of [-unit/2,0,unit/2]) line([0,q],[unit,0]);
      if(one||kind==="erZeroOne") line([many?unit*1.3:unit*.4,-unit/2],[many?unit*1.3:unit*.4,unit/2]);
      if(zero) { const [x,y]=point(unit*1.6,0);c.ellipse(x-unit*.35,y-unit*.35,unit*.7,unit*.7);c.stroke(); }
    };
  });
}
