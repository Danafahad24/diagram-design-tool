---
name: diagram

description: Create editable diagrams in chat with the Canvas Diagram Designer. Use whenever the user asks for a diagram, flowchart, swimlane, process/workflow, approval flow, architecture or system diagram, network diagram, UML diagram, use case diagram, class diagram, sequence diagram, activity diagram, state diagram, ER diagram, mind map, org chart, or BPMN-style diagram. Identify the requested diagram type first and follow the correct notation for that type instead of converting every request into a generic architecture or workflow diagram.

triggers:
  keywords:
    [
      diagram,
      flowchart,
      flow chart,
      process diagram,
      workflow diagram,
      approval flow,
      decision flow,
      swimlane,
      swimlane diagram,
      architecture diagram,
      system diagram,
      network diagram,
      er diagram,
      erd,
      uml,
      use case,
      use case diagram,
      class diagram,
      sequence diagram,
      activity diagram,
      state diagram,
      mind map,
      org chart,
      bpmn,
      مخطط,
      مخططات,
      رسم بياني,
      رسمة,
      خريطة ذهنية,
      مخطط انسيابي,
      خارطة تدفق,
      دورة العمل,
      مسار عمل,
      مخطط حالات الاستخدام,
      مخطط تسلسلي,
      مخطط فئات,
      مخطط معماري,
      هيكل,
      هيكلية
    ]
---

# Diagram Skill — Canvas Diagram Designer

Use `create_canvas_diagram` whenever the user asks for an editable diagram.

The tool returns the diagram editor itself as a Rich UI inside Open WebUI. The
user can move, resize, reconnect, rename, and restyle elements after generation.

The most important rule is:

> Identify the requested diagram type first, then follow the conventions of that
> diagram type.

Do not turn every request into an architecture diagram.
Do not turn every request into a generic workflow.
Do not mix notations from different diagram types unless the user explicitly asks
for a hybrid diagram.

If the user explicitly names a diagram type, preserve that type.

---

# 1. Choose the diagram type first

Before creating elements, determine what kind of diagram the user actually needs.

Use these routing rules when the user does not explicitly name the type:

- Actors + goals/interactions with a system → **Use Case Diagram**
- Roles/teams/systems responsible for different process steps → **Swimlane Diagram**
- Sequential process with decisions → **Flowchart**
- Formal business process with events/gateways/pools → **BPMN**
- Services/APIs/databases/infrastructure/integrations → **Architecture Diagram**
- Entities/tables/keys/relationships → **ER Diagram**
- Classes/attributes/methods → **UML Class Diagram**
- Participants/messages over time → **Sequence Diagram**
- Activities/decisions/parallel control flow → **Activity Diagram**
- States and transitions → **State Diagram**
- Hierarchical ideas/topics → **Mind Map**
- Reporting structure → **Org Chart**

If more than one type could work, choose the type that best matches the user's
stated purpose.

Do not create multiple diagram types unless the user asks for multiple diagrams.

---

# 2. Diagram structure

Describe diagrams using `elements` and `connections`.

Each element requires:

- a unique `id`
- a supported `type`
- `text`
- `x`
- `y`
- `width` and `height` when the defaults are not appropriate

Each connection requires:

- a unique `id`
- `source`
- `target`

Optional connection fields may include:

- `label`
- `style`
- arrowheads
- line type
- dashed style

Never:

- reuse ids
- reference an element that does not exist
- create a self-connection unless explicitly required
- invent unsupported element types
- create an invisible/placeholder element just to bend a connection's route
- merge several unrelated relationships into one shared connector
- route a connection through the center of an element it does not connect to

Keep arrowhead size and line thickness consistent across one diagram, and
avoid unnecessary connector crossings where a cleaner layout is available.

---

# 3. Layout and coordinates

`x`/`y` is the top-left corner of the element, in the same units as `width`/
`height`. The editor auto-fits whatever bounding box the elements occupy, so
there is no fixed canvas size to stay inside — the risk is not "off canvas",
it is inconsistent scale: spreading a few elements across a huge empty area
zooms everything out and shrinks the text, while cramming many elements
together overlaps them.

Rules:

- Default element size is 160×80. Size custom shapes proportionally to that
  — do not mix elements sized in the tens with elements sized in the
  thousands in the same diagram.
- Leave 60–120 units of clear space between adjacent element edges (not
  between their `x`/`y` origins) so labels and connection routing have room.
- Two elements' bounding boxes must never overlap unless one is a container
  (`pool`, `swimlane`, `system_boundary`) deliberately holding the other.
- Lay elements out on the axis the diagram type calls for — top-to-bottom for
  a sequence of steps over time (flowchart, activity, sequence, state,
  BPMN), left-to-right for a request/data path (architecture) or peer
  relationships (ER, class), radiating outward from a center (mind map), or
  strictly by hierarchy level (org chart, use case). See the per-type
  sections below for which axis applies.
- Keep spacing consistent across one diagram; do not tighten it for some
  elements and loosen it for others without a reason tied to the content.

---

# 4. Supported element types

## Flowchart

Use:

- `start_end`
- `process`
- `decision`
- `document`
- `data`
- `subprocess`

## Architecture

Use:

- `server`
- `database`
- `cloud`
- `api`
- `service`
- `queue`
- `container`
- `code`
- `user`
- `actor`
- `image`

## UML / ERD

Use:

- `class`
- `entity`
- `table`
- `use_case`
- `package`
- `note`
- `system_boundary`
- `lifeline`
- `activation`
- `state`
- `initial_state`
- `final_state`
- `fork_join`

## BPMN

Use:

- `bpmn_start_event`
- `bpmn_intermediate_event`
- `bpmn_end_event`
- `bpmn_task`
- `bpmn_subprocess`
- `bpmn_exclusive_gateway`
- `bpmn_parallel_gateway`
- `bpmn_inclusive_gateway`
- `pool`

## General / Basic

Use:

- `rectangle`
- `rounded_rectangle`
- `circle`
- `ellipse`
- `diamond`
- `triangle`
- `hexagon`
- `double_ellipse`
- `text`

For grouped process ownership, use `swimlane` or `pool` with a `lanes` list.

For `class`, `entity`, and `table`, put each row on its own line in `text`.

For a UML class, use a line containing only:

`---`

to separate attributes from operations.

---

# 5. Diagram-specific conventions

## Use Case Diagram

Use proper UML use-case notation.

Rules:

- Human or external actors must be outside the system boundary.
- Use `actor` for actors.
- Use `system_boundary` for the system.
- Use `use_case` for use cases.
- Use cases belong inside the system boundary.
- Use-case elements should visually behave as UML use-case ovals.
- **Association** (actor uses a use case): one connection per actor/use-case
  pair, `line_type: "straight"`, `end_arrow: "none"`, `start_arrow: "none"`,
  no label needed. The default line type is `"orthogonal"` — leaving it
  unset routes several associations from the same actor as right-angle bends
  that visually fuse into one shared bracket/trunk. Always set `line_type`
  explicitly.
- **`«include»`** (base use case always triggers another): connect
  `source` = the including (base) use case → `target` = the included use
  case. `dashed: true`, `end_arrow: "open"`, `label: "«include»"`.
- **`«extend»`** (an optional use case extends a base one): connect
  `source` = the extending use case → `target` = the base use case being
  extended. `dashed: true`, `end_arrow: "open"`, `label: "«extend»"`. Note
  the direction is opposite in feel from include — extend points from the
  optional behavior back to the base it extends.
- **Generalization** (one actor or use case is a specialization of another):
  connect `source` = the child (specific) → `target` = the parent
  (general). Solid line, `end_arrow: "block"`, `end_fill: false`,
  `dashed: false` — a hollow triangle at the parent end, same convention as
  UML class inheritance.
- Use `«include»`/`«extend»`/generalization only when the user's request
  actually implies that relationship (a shared mandatory sub-step, an
  optional variant, or a genuine is-a specialization). Do not add them to
  make the diagram look more complete — an association is the default and
  usually correct choice.
- Keep the diagram focused on what actors want to achieve, not on how the
  system implements it.
- If the request doesn't give you enough to tell whether two use cases
  relate by include, extend, generalization, or nothing at all, ask a short
  clarifying question rather than inventing the relationship.

Do not represent backend infrastructure such as databases, queues, APIs, or
storage as ordinary use cases unless the user explicitly asks for a hybrid
technical diagram. Do not imply a step-by-step sequence (numbered arrows, a
left-to-right pipeline) — a use case diagram shows capabilities and actors,
not a process flow; use a flowchart or activity diagram for that.

Incorrect:

- putting actors inside the system boundary
- rendering use cases as architecture boxes
- showing databases as use cases
- laying everything out as a technical request pipeline, or numbering the
  use cases as if they were sequential steps
- leaving associations on default orthogonal routing so multiple lines from
  one actor merge into a single bent bracket instead of separate straight
  lines
- an `«include»`/`«extend»`/generalization arrow pointing the wrong way, or
  added where a plain association was all that was implied

---

## Swimlane Diagram

A swimlane diagram must contain actual lanes.

Rules:

- Use `swimlane` or `pool` with a `lanes` list.
- Each lane represents a responsible person, team, role, department, or system.
- Every process activity must appear inside the lane responsible for it.
- Show flow crossing lane boundaries when responsibility changes.
- Use process/task shapes inside the lanes.
- Use decision shapes for branching.
- Label branches clearly, such as:
  - Yes / No
  - Approved / Rejected
  - Valid / Invalid
- Keep lane labels visually separate from process activities.

A horizontal row of systems is NOT a swimlane diagram.

Do not create independent architecture boxes and call them lanes.

---

## Flowchart

Use standard flowchart semantics.

Rules:

- `start_end` → start/end
- `process` → action/process step
- `decision` → branching decision
- `data` → input/output
- `document` → document-related step
- `subprocess` → reusable/contained subprocess

Use a consistent flow direction.

Prefer:

- top-to-bottom for procedural flows
- left-to-right when requested or when it improves readability

Label every decision branch clearly.

Do not use architecture icons as substitutes for flowchart notation unless the
user specifically asks for a hybrid technical flow.

---

## Architecture Diagram

Use architecture notation for technical systems and integrations.

Typical elements:

- user/client
- frontend
- backend service
- API
- database
- object storage
- message queue
- model/AI service
- observability
- external service
- container/cloud/server

Rules:

- Show logical technical dependencies.
- Show request/data direction clearly.
- Separate primary data/request flow from secondary observability or management
  connections.
- Use dashed lines for secondary/tracing/control relationships when appropriate.
- Group related components when helpful.
- Prefer left-to-right for system request flow unless another layout is better.

Use technical icons only when they improve understanding.

Do not convert a requested swimlane, use case, ERD, or sequence diagram into an
architecture diagram.

---

## ER Diagram / ERD

Use ER notation, not process notation.

Rules:

- Use `entity` or `table`.
- Put the entity/table name first.
- Put attributes on separate lines.
- Identify primary keys and foreign keys when known.
- Use relationships between entities.
- Use correct cardinality where available.
- Size the box to fit every row — same formula as UML Class: with default
  `font_size` 14, `height` ≈ `30 + 21 × (number of attribute lines)`.
  Undersizing silently drops the bottom rows instead of showing them.

Supported ER connection arrowheads include:

- `erOne`
- `erMany`
- `erZeroOne`
- `erOneMany`
- `erZeroMany`

Example entity text:

```text
USERS
---
PK id
name
email
FK role_id
```

---

## UML Class Diagram

Use `class` for every class.

Rules:

- Line 1 of `text` is the class name.
- A line containing only `---` separates attributes (above) from operations
  (below), one member per line.
- Do not put behavior in the attributes half or fields in the operations half.
- Size the box to fit every row, or rows silently disappear rather than
  wrapping or shrinking. With the default `font_size` of 14: header height is
  30, each additional row is 21. Required `height` ≈ `30 + 21 × (number of
  lines after the class name, including the `---` line)`. If `font_size` is
  overridden to `s`, header ≈ `max(30, s + 16)` and row height ≈
  `max(20, s × 1.5)`. Round up, not down, when in doubt.

Relationships are plain connections with `style` set to the arrowheads below —
there is no relationship "kind" field, so the arrowheads themselves carry the
UML meaning. Connect `source` → `target` in the direction shown:

- **Association** (`A` uses `B`): `end_arrow: "none"`, `start_arrow: "none"`,
  `dashed: false`.
- **Dependency** (`A` depends on `B`): `end_arrow: "open"`, `dashed: true`.
- **Inheritance** (`A` extends `B`, source is the subclass): `end_arrow:
  "block"`, `end_fill: false`, `dashed: false`.
- **Realization** (`A` implements interface `B`): same as inheritance plus
  `dashed: true`.
- **Aggregation** (`A` is the whole, `B` the part — source is the whole):
  `start_arrow: "diamond"`, `start_fill: false`, `dashed: false`.
- **Composition** (`A` owns `B`'s lifetime — source is the whole):
  `start_arrow: "diamond"`, `start_fill: true`, `dashed: false`.

Never use ER arrowheads (`erOne`, `erMany`, ...) on a class diagram, and never
draw a class as a `use_case` oval.

---

## Sequence Diagram

A connection has no `y` of its own — its position on screen comes entirely
from the `x`/`y` of the two elements it connects. `lifeline` elements run the
full height of the diagram, so two messages that both connect
lifeline-directly-to-lifeline connect the same two points and land on top of
each other: same drawn position, same label position, unreadable overlapping
text. This is the single most common way a sequence diagram breaks. Never
connect a message directly between two `lifeline` elements.

Rules:

- One `lifeline` element per participant, placed left to right in the order
  participants first appear. A lifeline is the participant's header box with
  its dashed line already drawn down the column — do not draw that line
  yourself.
- Increasing `y` is later in time.
- Give every message its own short `activation` element on the sending
  lifeline's column and another on the receiving lifeline's column, each
  positioned (`x` lined up with that lifeline, `y` at the exact moment the
  message occurs, small `height`, e.g. 20–30). Connect the message between
  those two activations, not between the lifelines. Because each pair of
  activations sits at a different `y`, each message naturally lands at its
  own height instead of collapsing onto the last one.
- A participant that stays busy across several messages gets several
  adjacent/overlapping short activations stacked at the right heights rather
  than one giant activation spanning the whole diagram — a single tall
  activation is exactly what causes every message touching it to converge on
  one point.
- Message arrow styles:
  - **Synchronous call**: `end_arrow: "block"`, `end_fill: true`,
    `dashed: false`.
  - **Return**: `end_arrow: "open"`, `dashed: true`.
  - **Asynchronous message**: `end_arrow: "open"`, `dashed: false`.
- A self-message (a participant calling itself) is one of the few cases where
  a connection may share `source` and `target` — use two activations on the
  same lifeline, one just above the other.
- Never route a message through a third lifeline it does not target.
- Free-floating annotations (e.g. "verify password hash") belong as a `note`
  element connected to the activation or message it explains — a `note` left
  unconnected off to the side reads as unrelated to the flow.

---

## Activity Diagram

Rules:

- Start with `initial_state` (filled circle) and end with one or more
  `final_state` elements (circle-in-circle).
- Use `process` or `rounded_rectangle` for actions.
- Use `decision` for branches and label every branch (Yes/No, etc.), same as
  a flowchart.
- Use `fork_join` for both the parallel split and the parallel merge: one
  `fork_join` element with multiple outgoing connections starts concurrent
  flows, another `fork_join` with multiple incoming connections rejoins them.
- Keep one consistent direction (top-to-bottom or left-to-right); do not mix.

---

## State Diagram

Rules:

- Start with `initial_state` (filled circle). End with `final_state`
  (circle-in-circle). A diagram may have several final states but only one
  initial state.
- Represent each named state with the `state` type, labeled with the state
  name. Do not use `process`, `class`, or `entity` for a state.
- Every transition is a connection labeled with the triggering event or
  condition, `end_arrow: "open"` or `"classic"`, not dashed.
- A state may transition to itself (self-connection allowed here, same as a
  sequence diagram self-message).
- Do not model states as flowchart `decision` diamonds; a decision is a
  branch point, not a state the system stays in.

---

## BPMN

Rules:

- `bpmn_start_event` / `bpmn_intermediate_event` / `bpmn_end_event` for
  events; `bpmn_task` for a single activity; `bpmn_subprocess` for a
  collapsed/expandable activity.
- `bpmn_exclusive_gateway` (XOR — exactly one outgoing path taken),
  `bpmn_parallel_gateway` (AND — every outgoing path taken),
  `bpmn_inclusive_gateway` (OR — one or more outgoing paths taken). Label the
  outgoing connections of an exclusive or inclusive gateway with the
  condition that selects them.
- `pool` for a top-level participant, with a `lanes` list for the roles or
  systems inside it — same lane discipline as a swimlane diagram: every task
  belongs inside the lane responsible for it.
- Use a plain solid connection for sequence flow within a pool, and a dashed
  connection for message flow between separate pools.
- Do not substitute `start_end`/`process`/`decision` flowchart shapes for
  BPMN events, tasks, and gateways once the user has asked for BPMN.

---

## Mind Map

Rules:

- One central node (the topic) with branches radiating outward; use
  `ellipse` or `rounded_rectangle` for the topic and its child nodes.
- Connections are unlabeled, `end_arrow: "none"`, `line_type: "curved"`.
- Group related branches by proximity and, optionally, a shared `style.fill`
  per branch rather than by boxing them in a container shape.
- Do not add decision diamonds, swimlanes, or directional arrowheads — a mind
  map has no process flow or sequencing.

---

## Org Chart

Rules:

- One `rectangle` or `rounded_rectangle` per person or role, with the title
  (and name, if given) in `text`.
- Connections run manager → report, `end_arrow: "none"`, `line_type:
  "orthogonal"`, unlabeled.
- Lay out strictly top-to-bottom by reporting level; do not place a report
  above or beside their manager.
- Do not use dashed lines for solid-line reporting relationships; reserve
  dashed connections only if the user explicitly asks for a dotted-line
  (matrix/indirect) reporting relationship.