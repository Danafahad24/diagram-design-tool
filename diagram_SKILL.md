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

---

# 3. Supported element types

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

For grouped process ownership, use `swimlane` or `pool` with a `lanes` list when
supported by the request schema.

For `class`, `entity`, and `table`, put each row on its own line in `text`.

For a UML class, use a line containing only:

`---`

to separate attributes from operations.

---

# 4. Diagram-specific conventions

## Use Case Diagram

Use proper UML use-case notation.

Rules:

- Human or external actors must be outside the system boundary.
- Use `actor` for actors.
- Use `system_boundary` for the system.
- Use `use_case` for use cases.
- Use cases belong inside the system boundary.
- Use-case elements should visually behave as UML use-case ovals.
- Connect actors to use cases with association lines.
- Use include/extend relationships only when semantically appropriate.
- Keep the diagram focused on what actors want to achieve.

Do not represent backend infrastructure such as databases, queues, APIs, or
storage as ordinary use cases unless the user explicitly asks for a hybrid
technical diagram.

Incorrect:

- putting actors inside the system boundary
- rendering use cases as architecture boxes
- showing databases as use cases
- laying everything out as a technical request pipeline

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

Rules:

- One `lifeline` element per participant, placed left to right in the order
  participants first appear. A lifeline is the participant's header box with
  its dashed line already drawn down the column — do not draw that line
  yourself and do not connect anything to extend it.
- Increasing `y` is later in time. Never place a message above a lifeline
  element it happens after.
- An `activation` element is a bar laid directly on top of a lifeline's
  column for the span that participant is active — position it by `x`/`y`/
  `height` to line up with that lifeline; it is not a connection endpoint.
- Every message is a connection between two `lifeline` elements, labeled with
  the message text, positioned at the `y` when it occurs:
  - **Synchronous call**: `end_arrow: "block"`, `end_fill: true`,
    `dashed: false`.
  - **Return**: `end_arrow: "open"`, `dashed: true`.
  - **Asynchronous message**: `end_arrow: "open"`, `dashed: false`.
- A self-message (a participant calling itself) is one of the few cases where
  a connection may share `source` and `target`.
- Never route a message through a third lifeline it does not target.

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
- Represent each named state as a `rounded_rectangle` labeled with the state
  name — there is no dedicated "state" shape, so do not use `process`,
  `class`, or `entity` for a state.
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
FK role_id