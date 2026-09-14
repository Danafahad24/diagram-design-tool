---
name: diagram

description: Create editable diagrams in chat with the Canvas Diagram Designer. Use whenever the user asks for a diagram, flowchart, swimlane, process/workflow, approval flow, architecture or system diagram, network diagram, UML diagram, use case diagram, class diagram, sequence diagram, activity diagram, ER diagram, mind map, org chart, or BPMN-style diagram. Identify the requested diagram type first and follow the correct notation for that type instead of converting every request into a generic architecture or workflow diagram.

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