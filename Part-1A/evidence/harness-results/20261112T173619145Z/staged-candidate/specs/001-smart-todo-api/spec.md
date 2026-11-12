# Feature Specification: Smart Todo & Task Management API

**Feature Branch**: `001-smart-todo-api`

**Created**: 2026-11-11

**Status**: Draft - Pending Human Review

**Version**: 1.3.0

**Input**: User description: "Create a deterministic task-management API with task CRUD, tag filtering, priority sorting, JSON persistence, and validated task-status transitions."

## Clarifications

### Session 2026-11-11

- Q: Should the specification require a single running API instance to serialize concurrent task mutations, including ID allocation and read-modify-write persistence? → A: Yes; serialize all task mutations within one application instance.
- Q: When stored JSON is malformed, should the application stay available and return the documented `500 malformed_stored_data` response to API requests, or should it refuse to start until the store is repaired? → A: Start normally and return the documented API error when a request accesses the malformed store.

### Session 2026-11-12

- Q: Which harness artifacts are trusted: the copies submitted in Part-1A or a separately protected baseline? → A: Part-1A tests, harness scripts, controls, and evidence are required submitted copies but are untrusted candidates/evidence. Only a canonical runner that verifies their exact SHA-256 digests against the separately protected baseline may stage and execute them. Repository location alone establishes no trust; D-01 remains blocked unless the separate identity/ACL or protected CI boundary is demonstrated.
- Q: How are instruction files that influence coding or validation selected? → A: Enumerate only actual files in `.harness/instruction-files.json`, with `path`, `purpose`, `classification`, `sha256`, and `approval_reference` keys. Do not use wildcard entries. Protect the inventory and listed digests through the trusted baseline and approval process.
- Q: Who reviews Bandit findings? → A: The runner executes Bandit and preserves its machine-readable findings and execution output. A human security reviewer reviews each finding, records its resolution or documented disposition with identity, date, and rationale, and determines whether the review gate is satisfied.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage Tasks (Priority: P1)

As a person maintaining a todo list, I can create, retrieve, update, list, and
delete tasks so that the task collection reflects my current work.

**Why this priority**: Task lifecycle operations are the minimum useful task
management capability.

**Independent Test**: Exercise the task endpoints against an empty collection,
complete a create/read/update/delete lifecycle, and verify the returned records
and collection state.

**Acceptance Scenarios**:

1. **Given** an empty collection, **When** I create a task with a title,
   **Then** the API returns the created task and its unique identifier (AC-001,
   AC-002).
2. **Given** an existing task, **When** I retrieve it, update its details, list
   tasks, or delete it, **Then** each response and resulting state match the API
   contract (AC-003, AC-004, AC-005).
3. **Given** a missing task or invalid input, **When** I request or change that
   task, **Then** the API returns the documented error status and envelope
   (AC-018, AC-019, AC-020).

### User Story 2 - Organize and Find Tasks (Priority: P2)

As a person with multiple tasks, I can add tags, filter by tags, and sort by
priority so that I can find and order relevant work predictably.

**Why this priority**: Tags and priority make a growing task collection easier to
scan without adding unrelated task-management features.

**Independent Test**: Create tasks with overlapping tags and all priority values;
verify tag matching, empty results, default order, priority order, and tie order.

**Acceptance Scenarios**:

1. **Given** tasks with different tags, **When** I filter with one or more tags,
   **Then** only tasks containing every requested tag are returned (AC-006,
   AC-007).
2. **Given** tasks at different priorities and a priority tie, **When** I request
   priority sorting, **Then** tasks use the documented priority order and stable
   tie-breaker (AC-008, AC-009).
3. **Given** no matching tasks, **When** I filter the collection, **Then** the
   API returns a successful empty result (AC-007).

### User Story 3 - Track Task Progress (Priority: P2)

As a person working through tasks, I can move a task through permitted statuses
and receive a clear rejection for a prohibited transition.

**Why this priority**: Explicit transitions keep progress meaningful and prevent
invalid task state changes.

**Independent Test**: Submit each allowed and prohibited transition and verify the
response status and stored task status.

**Acceptance Scenarios**:

1. **Given** a Pending task, **When** I move it to In Progress and then Completed,
   **Then** both permitted transitions succeed (AC-010, AC-011).
2. **Given** a transition not in the permitted sequence, **When** I request it,
   **Then** the API returns a conflict and leaves the task unchanged (AC-012).

### User Story 4 - Keep Tasks Across Restarts (Priority: P1)

As a person relying on a local task list, I can restart the API without losing
valid tasks, and data errors do not silently erase my collection.

**Why this priority**: Persistence is essential for a task list to remain useful
between API runs.

**Independent Test**: Create data, restart the application using the same local
store, and verify the data; separately inject malformed data and a write failure
and verify the documented errors and preservation guarantees.

**Acceptance Scenarios**:

1. **Given** valid stored tasks, **When** the API is restarted, **Then** the same
   tasks remain available (AC-013).
2. **Given** a failed write or malformed stored JSON, **When** the API accesses
   the store, **Then** it reports the documented error and does not partially
   replace or silently reset the original data (AC-014, AC-015).

### Edge Cases

- An empty collection and a filter with no matches both return HTTP 200 with
  `items: []` and `count: 0`.
- A title containing only whitespace, a title beyond its maximum length, or a
  title of the wrong type is rejected.
- Optional descriptions may be omitted or null on creation; an update may set a
  description to null to clear it.
- Tag comparison is case-insensitive after normalization; duplicate normalized
  tags occur only once in the task.
- More than one filter tag uses AND semantics; duplicate filter tags are treated
  as one tag.
- Invalid priority or status values are validation errors; a valid but prohibited
  status transition is a conflict.
- An invalid task ID format is rejected as input; a well-formed ID for a missing
  task returns not found.
- Malformed request JSON, a valid JSON body with invalid fields, malformed stored
  JSON, and local write failures have distinct documented error codes.
- The application starts with a malformed store; requests that access it return
  the documented `malformed_stored_data` error without changing the store.
- If an atomic replacement fails, the pre-existing store remains byte-for-byte
  unchanged.
- Concurrent mutations handled by one application instance are serialized;
  concurrent writers from independent application processes are outside scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The API MUST create a task from a request containing a title and
  optional description, tags, and priority.
- **FR-002**: The API MUST assign each created task a deterministic positive
  integer identifier, starting at 1 and increasing by 1 for each successful
  creation. An identifier MUST NOT be reused after deletion or restart.
- **FR-003**: The API MUST retrieve a task by identifier and return not found when
  no task has that identifier.
- **FR-004**: The API MUST list every task in the collection; pagination is not
  part of this feature.
- **FR-005**: The API MUST allow partial updates to title, description, tags, and
  priority while leaving omitted fields unchanged. Status changes use the
  dedicated status endpoint.
- **FR-006**: The API MUST delete an existing task and make it unavailable to
  subsequent reads.
- **FR-007**: A task MUST support multiple tags. Tags MUST be trimmed,
  case-normalized to lowercase, deduplicated, and returned in lexicographic
  order.
- **FR-008**: The task list MUST accept one or more repeated `tag` query
  parameters. When multiple tags are supplied, a task matches only if it contains
  every requested tag. A zero-match query MUST return HTTP 200 with an empty
  `items` array and `count` 0.
- **FR-009**: Priority MUST be one of `Low`, `Medium`, or `High`. If omitted on
  creation, priority MUST default to `Medium`.
- **FR-010**: The task list MUST support priority sorting in `High`, `Medium`,
  `Low` order. Equal priorities MUST sort by numeric task ID ascending. Without
  priority sorting, tasks MUST sort by numeric task ID ascending.
- **FR-011**: Task status MUST be one of `Pending`, `In Progress`, or
  `Completed`. A newly created task MUST have status `Pending`; clients cannot
  supply status in the create request.
- **FR-012**: The only status transitions that change state MUST be
  `Pending -> In Progress` and `In Progress -> Completed`. Requesting the
  current status MUST succeed as an idempotent no-op. Every other transition
  between different statuses MUST be rejected without changing the task.
- **FR-013**: The API MUST persist the task collection and next task identifier
  in a local JSON document and preserve them across application restarts. A
  missing store MUST represent an empty collection with next identifier 1, not
  an error.
- **FR-014**: Every persistence write MUST serialize a complete replacement to a
  temporary file in the same directory and atomically replace the store only
  after the temporary file is complete. If a write or replacement fails, the
  previous store and corresponding in-memory state MUST remain unchanged, and
  the API MUST report a persistence error.
- **FR-015**: Malformed stored JSON or an invalid stored-data shape MUST raise
  the typed `MalformedStoredDataError` with stable identifier
  `malformed_stored_data`. This includes invalid task records, duplicate IDs, or
  a non-positive next identifier or one that is not greater than every task ID
  present in the store. The API process MUST start successfully even if the
  existing store is malformed. Store validation MUST occur on request access,
  not during process startup; each request that accesses a malformed store MUST
  return the documented `500 malformed_stored_data` error. The original store
  MUST remain unchanged and MUST NOT be silently reset, replaced, or overwritten.
- **FR-016**: The API MUST validate request bodies, path identifiers, and query
  parameters according to the rules in this specification. Unknown body fields
  MUST be rejected.
- **FR-017**: Each endpoint MUST use the method, request fields, response shape,
  and HTTP status codes defined in the API Contract section.
- **FR-018**: Every API error MUST use the common error envelope defined below
  and MUST NOT expose stack traces, local file paths, or internal implementation
  details. Each field-level detail MUST contain exactly the string fields
  `field`, `code`, and `message`; details MUST be ordered by field path, with
  `code` and then `message` as deterministic tie-breakers. Errors without
  field-level information MUST use an empty details array.

### Non-Functional Requirements

- **NFR-001**: Sequential requests against identical persisted state, including
  the next task identifier, MUST produce the same status, response data, and
  ordering. Repeating the same sequential request sequence from identical
  initial state MUST produce identical results. Business behavior MUST NOT
  depend on random identifier generation, external AI services, or unpredictable
  network calls. Concurrent mutation ordering and request-to-ID assignment are
  governed by NFR-007.
- **NFR-002**: The project target is Python 3.12 with FastAPI and Pydantic.
  API routes, business logic, data models, and persistence MUST remain separate;
  routes MUST NOT access JSON files directly, and business logic MUST NOT depend
  on API routes. No unrequested application subsystems or external runtime
  services are in scope.
- **NFR-003**: Secrets, credentials, private keys, and local environment files
  MUST NOT be committed. The application MUST validate untrusted input, avoid
  unsafe execution, and avoid exposing internal stack traces in responses. A
  final repository security review MUST be recorded before publication and MUST
  include repository hygiene findings and their disposition.
- **NFR-004**: Every functional requirement and acceptance criterion MUST map to
  at least one automated test. The tests MUST include positive, negative,
  boundary, and invalid-input cases where applicable. All mandatory automated
  tests MUST pass. Ruff MUST report zero lint violations. The automated runner
  MUST execute Bandit and preserve its exit code, stdout, stderr, machine-readable
  findings, and execution status. A human security reviewer MUST review each
  finding and record its resolution or documented disposition, reviewer
  identity, date, and rationale before acceptance; automated execution MUST NOT
  create or impersonate this review.
- **NFR-005**: Automated application tests MUST NOT rely on external network
  services. Part-1A MUST retain the assignment-required submitted repository
  copies of tests, `.harness/` scripts and controls, and evidence. These
  repository copies are untrusted candidates or evidence; repository location
  alone MUST NOT establish trust, and a submitted copy MUST NOT be authoritative
  merely because it is outside application source.

  The authoritative boundary MUST consist of a canonical trusted runner, the
  canonical test/control baseline, approval records, and a protected execution
  environment administered through a separate Windows identity/ACL or
  protected CI controls. Before each authoritative run, the trusted runner MUST
  verify the exact SHA-256 digests of the submitted runner, mandatory tests,
  expected results, validation controls, and instruction inventory against the
  separately protected, human-approved baseline. It MUST verify each inventoried
  instruction file against the controlled inventory and approved digests, then
  stage and execute only the verified immutable snapshot. Missing/invalid
  baselines or approval records, unauthorized modifications, and digest
  mismatches MUST fail closed with a non-zero exit code and MUST NOT produce a
  success-shaped result. If the separately administered identity/ACL or
  protected CI boundary cannot be demonstrated, D-01 remains blocked and no
  authoritative validation is permitted.

  `.harness/instruction-files.json` MUST inventory only actual instruction or
  governing files that influence coding-agent behavior or validation. Each
  entry MUST contain the keys `path`, `purpose`, `classification`, `sha256`, and
  `approval_reference`, with the exact file path, purpose and classification,
  digest, and human approval reference. Wildcard paths MUST NOT be used. The
  inventory itself and each listed file MUST be included in the validation
  candidate manifest and trusted baseline workflow. Changes to inventoried
  files or their inventory entries require recorded human approval of the
  exact change and new digests before the protected baseline is updated.
  Authoritative results MUST be generated by the runner and MUST NOT be
  manually edited.
- **NFR-006**: Preserve initial and final implementations, test and security
  results, failure evidence, and repair history. Automated validation MUST report
  only its check results and MUST NOT set or infer the final ACCEPT or REJECT
  decision. After reviewing the final implementation and evidence, a human MUST
  record an explicit ACCEPT or REJECT. Automated PASS is not acceptance.
- **NFR-007**: Mutating requests handled by one application instance MUST be
  serialized across task updates and persistence. Each response and the final
  store MUST correspond to a serial execution of those requests. Concurrent
  creates MUST receive unique sequential IDs, and successful mutations MUST NOT
  be lost. The particular concurrent request assigned each ID is unspecified.
  If persistence fails, the corresponding in-memory state change MUST NOT be
  committed; the prior in-memory and persisted states MUST remain unchanged.

### API Contract

#### Task Representation

A successful task response contains exactly these fields:

```json
{
  "id": 1,
  "title": "Pay bill",
  "description": null,
  "tags": [],
  "priority": "Medium",
  "status": "Pending"
}
```

The collection response is:

```json
{
  "items": [],
  "count": 0
}
```

`count` MUST equal the number of tasks in `items`. The response always includes
all task fields; an absent description is represented as `null`.

#### Endpoints

| Method and path | Request | Success response | Documented error statuses |
|---|---|---|---|
| `POST /tasks` | JSON object with `title`; optional `description`, `tags`, `priority` | `201 Created`, task representation, and `Location` header for the task | `400`, `422`, `500` |
| `GET /tasks` | Optional repeated `tag`; optional `sort=priority` | `200 OK`, collection representation | `422`, `500` |
| `GET /tasks/{id}` | Positive decimal integer path value | `200 OK`, task representation | `404`, `422`, `500` |
| `PATCH /tasks/{id}` | Non-empty JSON object with one or more mutable detail fields | `200 OK`, updated task representation | `400`, `404`, `422`, `500` |
| `DELETE /tasks/{id}` | Positive decimal integer path value; no request body | `204 No Content`, no response body | `404`, `422`, `500` |
| `PATCH /tasks/{id}/status` | JSON object containing `status` | `200 OK`, updated task representation | `400`, `404`, `409`, `422`, `500` |

Malformed JSON request syntax returns `400`. A syntactically valid body or query
with invalid or missing fields returns `422`. A well-formed identifier that
does not identify a task returns `404`. A valid but prohibited status transition
returns `409`. Stored-data and persistence failures return `500`.

#### Validation Rules

- `title` MUST be a string with 1 to 200 characters after trimming leading and
  trailing whitespace. Whitespace-only titles are invalid. The trimmed title is
  stored and returned.
- `description` MAY be omitted or null on creation. A supplied description MUST
  be a string of 0 to 2,000 characters. On update, null clears the description.
- `tags` MAY be omitted and defaults to an empty list. A supplied list MUST
  contain no more than 20 entries. Each entry MUST be a string that, after
  trimming and lowercasing, contains 1 to 32 characters. Duplicate normalized
  values are collapsed.
- `priority` MUST exactly match one of `Low`, `Medium`, or `High`.
- `status` MUST exactly match one of `Pending`, `In Progress`, or `Completed`;
  it is accepted only by the status endpoint.
- A detail update MUST contain at least one permitted field. Unrecognized fields,
  including `status` on the detail endpoint, are invalid.
- Path IDs MUST be positive base-10 integers without leading zeros. `sort`
  accepts only `priority`.
  Repeated `tag` query values use the same tag normalization and bounds as task
  tags; duplicate normalized filters are collapsed. Unknown query parameters
  are rejected.

#### Error Response

Every error response uses this shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```

`details` is always an array of field-specific details, or an empty array when
no field-level information applies. Each detail object has exactly three
required string fields: `field` (the field path), `code` (a field error
code), and `message` (a stable client-facing description). Unknown detail
fields are not allowed. Details are ordered by `field` in ascending
lexicographic order; details with the same `field` are ordered by `code`, then
`message`, in ascending lexicographic order. Error codes are stable:

| HTTP status | Error code | Meaning |
|---|---|---|
| `400` | `invalid_json` | Request body is not valid JSON |
| `404` | `not_found` | The requested task does not exist |
| `409` | `invalid_status_transition` | A valid status value is not permitted from the current status |
| `422` | `validation_error` | Request fields, path ID, or query parameters are invalid |
| `500` | `malformed_stored_data` | Stored JSON or stored task data is malformed |
| `500` | `persistence_error` | A local persistence operation failed |

Error messages MUST be stable and suitable for clients. They MUST NOT contain
stack traces, local file paths, or other internal implementation details.

#### Local JSON Document

The JSON document MUST be an object with a positive integer `next_id` and a
`tasks` array. The next successful creation uses `next_id` and increments it by
one in the same persisted replacement as the new task. Deletion MUST NOT
decrement or reuse `next_id`. The `tasks` entries use the Task Representation
fields above. For example:

```json
{
  "next_id": 2,
  "tasks": [
    {
      "id": 1,
      "title": "Pay bill",
      "description": null,
      "tags": [],
      "priority": "Medium",
      "status": "Pending"
    }
  ]
}
```

The persistence layer MUST validate the entire document before using or
replacing it. The root object MUST contain exactly `next_id` and `tasks`;
`next_id` MUST be a positive JSON integer (a Boolean is not an integer for this
contract), and `tasks` MUST be a JSON array. Duplicate JSON object member names
and unknown or missing fields are invalid.

Each task entry MUST be an object containing exactly `id`, `title`,
`description`, `tags`, `priority`, and `status`, with these rules:

- `id` MUST be a positive JSON integer, not a Boolean, and MUST be unique among
  all task entries.
- `title` MUST be a string of 1 to 200 characters, MUST NOT be blank, and MUST
  already be trimmed.
- `description` MUST be null or a string of 0 to 2,000 characters.
- `tags` MUST be an array of no more than 20 distinct strings. Each tag MUST be
  trimmed, lowercase, and 1 to 32 characters. The array MUST be in
  lexicographic order.
- `priority` MUST be exactly `Low`, `Medium`, or `High`.
- `status` MUST be exactly `Pending`, `In Progress`, or `Completed`.

`next_id` MUST be greater than every task ID in the document. Any invalid JSON,
root shape, field name, field type, field value, duplicate member name,
duplicate task ID, or identifier-counter relationship MUST raise
`MalformedStoredDataError` with identifier `malformed_stored_data`. The API MUST
return the documented `500` error without exposing stored content or internal
paths. It MUST NOT silently reset, repair, replace, or overwrite the invalid
store; the original bytes MUST remain unchanged until an explicit external
repair. A missing file represents `next_id: 1` and an empty task array.

### Key Entities

- **Task**: One item in the local task collection. It has a unique identifier,
  title, optional description, zero or more tags, one priority, and one status.
- **Task Collection**: The complete set of tasks returned by the list endpoint
  and preserved in the local JSON document.

### Acceptance Criteria

Each criterion below is binary: its associated automated test passes only when
all stated outcomes are observed.

- **AC-001**: A valid task creation returns `201`, a complete task
  representation, a `Location` header, and the specified defaults for omitted
  optional fields.
- **AC-002**: Creating two tasks from an empty store produces IDs 1 and 2;
  repeating the same creation sequence from the same initial persisted state
  produces the same IDs. After deletion and restart, a new task receives the
  next unused ID rather than reusing a prior ID.
- **AC-003**: Existing-task retrieval returns `200` and that task; list returns
  `200`, all tasks, the correct count, and an empty collection shape when there
  are no tasks. A well-formed unknown ID returns `404`.
- **AC-004**: A partial detail update returns `200`, changes every supplied
  permitted field, and preserves every omitted field. An empty update is
  rejected with `422`.
- **AC-005**: Deleting an existing task returns `204` with no body; subsequent
  retrieval and deletion of that ID return `404`.
- **AC-006**: Creating and updating tags returns trimmed lowercase tags,
  deduplicated and sorted lexicographically.
- **AC-007**: A single-tag filter returns exactly matching tasks; a multi-tag
  filter returns exactly tasks containing all normalized requested tags; no
  match returns `200`, `items: []`, and `count: 0`.
- **AC-008**: Each of `Low`, `Medium`, and `High` is accepted; omitted priority
  returns `Medium`; any other value returns `422`.
- **AC-009**: Priority-sorted results are ordered `High`, `Medium`, `Low`, with
  each equal-priority group ordered by ID ascending. Unsorted results are ordered
  by ID ascending.
- **AC-010**: A new task has status `Pending`; all three documented statuses
  appear in task responses.
- **AC-011**: `Pending -> In Progress` and `In Progress -> Completed` each return
  `200` and persist the requested status. Requesting the current status returns
  `200` without changing the task.
- **AC-012**: Each prohibited transition (`Pending -> Completed`,
  `In Progress -> Pending`, `Completed -> In Progress`, and
  `Completed -> Pending`) returns `409` with code
  `invalid_status_transition`; in every case the stored task remains unchanged.
- **AC-013**: After a task is written and the application is restarted against
  the same store, retrieving and listing returns the same task fields and values;
  the next successful creation receives the persisted next unused ID.
- **AC-014**: A successful write replaces the stored JSON, including tasks and
  next identifier, with a complete valid document. When a write or replacement
  is forced to fail, the API returns `500` with code `persistence_error`; the
  prior store remains byte-for-byte unchanged, and subsequent reads observe the
  unchanged in-memory task collection and next identifier.
- **AC-015**: Invalid stored JSON and a structurally invalid stored document
  raise `MalformedStoredDataError` with identifier `malformed_stored_data`.
  Table-driven cases cover malformed syntax; root type, keys, and duplicate
  members; missing or extra task fields; each task field's JSON type and bounds;
  Boolean-vs-integer IDs/counters; invalid tags, priorities, and statuses;
  duplicate task IDs; and invalid `next_id` relationships. For every case, the
  API process starts successfully; validation occurs on request access, and
  every request that accesses the malformed store returns `500` with that code,
  exposes no stack trace, and leaves the original store byte-for-byte unchanged.
- **AC-016**: Titles of 1 and 200 characters and descriptions of 0 and 2,000
  characters are accepted; a null description is accepted. Whitespace-only
  titles, non-string titles or descriptions, titles longer than 200 characters,
  and descriptions longer than 2,000 characters return `422`.
- **AC-017**: A list of 20 valid tags is accepted; 21 entries, an empty tag, a
  tag longer than 32 characters after normalization, or a non-string tag returns
  `422`. Case variants normalize to one tag.
- **AC-018**: Invalid JSON syntax returns `400` with code `invalid_json`.
  Invalid enum values, non-positive, non-decimal, or leading-zero IDs,
  unsupported query values, unknown request fields, and a non-object request
  body return `422` with code `validation_error`.
- **AC-019**: An automated contract test exercises each documented endpoint and
  verifies its success status, response shape, and applicable documented error
  statuses from the API Contract tables. Malformed JSON sent to either PATCH
  endpoint returns `400` with the existing `invalid_json` code.
- **AC-020**: Every tested error response has the documented envelope and stable
  code. Every field-level detail contains exactly the string fields `field`,
  `code`, and `message`, with no additional fields; details without field-level
  information are `[]`. Multiple details are ordered by ascending `field` path,
  then by `code` and `message` for ties. No error response contains a stack
  trace, local file path, or internal implementation detail.
- **AC-021**: Repeating the same sequential request sequence against identical
  persisted state, including the next identifier, returns identical status,
  task order, and response data, including identifiers returned by creation.
- **AC-022**: The validation record shows zero Ruff lint violations, all
  mandatory tests passing, at least one automated test mapped to every
  acceptance criterion, and Bandit execution with its exit code, stdout,
  stderr, machine-readable findings, and execution status captured. The
  validation process also preserves the initial and final implementations,
  results, failure evidence, and repair history. Automated
  application tests complete with external network access disabled and make no
  external network requests. Bandit finding dispositions are recorded in the
  separate human security review (AC-027). The runner records automated results
  only; it does not set or infer the final human decision.
- **AC-023**: Part-1A contains the required submitted repository copies of
  tests, `.harness/` scripts and controls, and evidence. These copies are
  untrusted candidates/evidence; repository location alone does not establish
  trust. Before validation, the canonical runner verifies exact SHA-256 digests
  for the submitted runner, mandatory tests, expected results, validation
  controls, `.harness/instruction-files.json`, and each inventoried instruction
  file against the separately protected, human-approved baseline and inventory.
  It executes only the verified immutable snapshot. The inventory contains no
  wildcard paths and each entry has the `path`, `purpose`, `classification`,
  `sha256`, and `approval_reference` keys. A missing or mismatched baseline,
  invalid approval record, or unauthorized modification is detected before
  application tests run; the runner records failure, produces no success-shaped
  result, and exits non-zero. If the separate identity/ACL or protected CI
  boundary cannot be demonstrated, D-01 remains blocked.
- **AC-024**: A legitimate change to a mandatory test, expected result, or
  validation control, instruction inventory, or inventoried instruction file is
  accepted only after a protected approval record contains the human approver,
  date, change rationale, and old/new SHA-256 digests, and the human-approved
  baseline is updated through a protected channel. A change without that record
  is rejected; a change matching the approved new baseline is accepted.
- **AC-025**: The selected runtime reports Python 3.12 and the API uses FastAPI
  and Pydantic. An automated architecture check verifies that routes depend on
  business logic rather than persistence details and that business logic does
  not depend on API routes.
- **AC-026**: The independent repository-hygiene scan detects representative
  local environment files, credentials, and private keys in synthetic fixtures
  created outside the publication file set, and reports zero such findings in
  the complete set of files intended for commit or publication. A finding
  blocks publication and cannot be suppressed by the application implementation.
- **AC-027**: Before publication, a human security review of the final repository
  records the repository-hygiene scan results and reviews each Bandit finding.
  For each finding, the reviewer records its resolution or documented
  disposition and rationale, along with reviewer identity, date, and reviewed
  repository scope. The human reviewer determines whether the review gate is
  satisfied. Publication is blocked until that complete human review record
  exists; automated execution or scans alone do not satisfy this criterion.
- **AC-028**: Automated validation never writes or infers `ACCEPT` or `REJECT`.
  After automated checks and the security review, a human records exactly one
  final decision with reviewer identity and date. The publication gate remains
  closed without that record and remains closed for `REJECT`.
- **AC-029**: Concurrent mutations within one application instance produce
  responses and a final store equivalent to a serial execution: no successful
  mutation is lost, created IDs are unique and sequential, and the persisted
  `next_id` is correct and is used by the next create after restart. The test
  does not assert which concurrent request receives which ID. A failed
  persistence operation returns `500` without committing its corresponding
  in-memory state change.

### Requirement-to-Test Traceability

Every FR and AC MUST have at least one automated test. The mapping below is the
minimum required coverage; additional focused tests MAY be added.

| Requirement | Acceptance criteria |
|---|---|
| FR-001 | AC-001 |
| FR-002 | AC-002, AC-029 |
| FR-003 | AC-003 |
| FR-004 | AC-003 |
| FR-005 | AC-004 |
| FR-006 | AC-005 |
| FR-007 | AC-006, AC-017 |
| FR-008 | AC-007 |
| FR-009 | AC-008 |
| FR-010 | AC-009 |
| FR-011 | AC-010 |
| FR-012 | AC-011, AC-012 |
| FR-013 | AC-013, AC-029 |
| FR-014 | AC-014, AC-029 |
| FR-015 | AC-015 |
| FR-016 | AC-016, AC-017, AC-018 |
| FR-017 | AC-019 |
| FR-018 | AC-020 |
| NFR-001 | AC-020, AC-021, AC-029 |
| NFR-002 | AC-025 |
| NFR-003 | AC-018, AC-020, AC-026, AC-027 |
| NFR-004 | AC-022, AC-027 |
| NFR-005 | AC-023, AC-024 |
| NFR-006 | AC-022, AC-027, AC-028 |
| NFR-007 | AC-014, AC-029 |

| Acceptance criterion | Minimum automated test assertion |
|---|---|
| AC-001 | AT-001: Create task with minimum and defaulted fields |
| AC-002 | AT-002: Assert repeatable IDs from equal initial state and no reuse after deletion/restart |
| AC-003 | AT-003: Retrieve existing/missing tasks and list empty/non-empty collections |
| AC-004 | AT-004: Partial update, field preservation, and empty update validation |
| AC-005 | AT-005: Delete task and verify subsequent not-found behavior |
| AC-006 | AT-006: Tag normalization, deduplication, and response order |
| AC-007 | AT-007: Single/multiple tag matching and zero-match response |
| AC-008 | AT-008: Priority enum, default, and invalid value |
| AC-009 | AT-009: Priority order, tie-break order, and default order |
| AC-010 | AT-010: Default and returned status values |
| AC-011 | AT-011: Allowed transitions and idempotent same-status request |
| AC-012 | AT-012: All prohibited transitions return conflict and preserve state |
| AC-013 | AT-013: Restart, read tasks, and continue the persisted ID sequence |
| AC-014 | AT-014: Verify atomic replacement and that failed writes preserve persisted bytes and in-memory state |
| AC-015 | AT-015: Verify successful startup, request-triggered validation, `500` on each malformed-store access, and unchanged bytes |
| AC-016 | AT-016: Title/description type and lower/upper boundary validation |
| AC-017 | AT-017: Tag count/length/type bounds and normalization |
| AC-018 | AT-018: Invalid JSON, IDs, queries, fields, enums, and body shape |
| AC-019 | AT-019: Endpoint contract checks, including malformed JSON on both PATCH routes |
| AC-020 | AT-020: Error envelope, exact field-detail schema, empty details when not applicable, deterministic ordering, and absence of internal details |
| AC-021 | AT-021: Repeat the same sequential request sequence from identical initial states and compare results |
| AC-022 | AT-022: Verify lint/tests/traceability, capture Bandit process output and machine-readable findings, verify network isolation and evidence, and ensure the runner does not decide acceptance |
| AC-023 | AT-023: Verify repository copies are untrusted, exact baseline and instruction-inventory digests are checked, only verified snapshots execute, and unauthorized changes fail non-zero |
| AC-024 | AT-024: Reject test/control/inventory/inventoried-file changes without protected human approval and accept only the approved new baseline |
| AC-025 | AT-025: Runtime/framework conformance and route/business/persistence boundary check |
| AC-026 | AT-026: Detect hygiene violations in fixtures and scan the publication file set |
| AC-027 | AT-027: Publication gate requires a human review of individual Bandit findings and recorded security dispositions |
| AC-028 | AT-028: Runner cannot set final decision; publication gate honors human ACCEPT/REJECT |
| AC-029 | AT-029: Verify serializable concurrent results, unique IDs, no lost updates, correct persisted next_id across restart, no request-to-ID ordering assumption, and no in-memory commit on persistence failure |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of task lifecycle scenarios in AC-001 through AC-005 return
  the documented status and leave the exact expected task state.
- **SC-002**: 100% of tag and priority fixtures in AC-006 through AC-009 return
  the expected task set and order.
- **SC-003**: 100% of valid and invalid status-transition cases in AC-010
  through AC-012 return the expected status and state.
- **SC-004**: 100% of persistence success and failure cases in AC-013 through
  AC-015 preserve or report persisted and in-memory data exactly as specified.
- **SC-005**: 100% of the functional requirements and acceptance criteria have
  corresponding automated checks, and all mandatory automated validation gates
  pass before human review.
- **SC-006**: 100% of files intended for publication have zero repository
  hygiene findings, and the final human security review and acceptance decision
  are recorded separately from automated validation. Publication is blocked
  unless the human decision is `ACCEPT`.
- **SC-007**: 100% of concurrent-mutation validation cases produce serializable
  results, lose no successful mutations, assign unique sequential IDs, persist
  the correct next ID across restart, and do not assert which concurrent request
  receives which ID.
- **SC-008**: 100% of tested field-level error details conform exactly to the
  documented schema and deterministic ordering; errors without field-level
  information return an empty details array.

## Assumptions

- The API manages one local task collection; user accounts, authentication,
  multi-user ownership, collaboration, and remote synchronization are outside
  this feature.
- The list endpoint returns all tasks; pagination, free-text search, due dates,
  reminders, recurring tasks, subtasks, and task history are outside scope.
- Tags use AND matching when more than one filter is supplied.
- Priority sorting always places High before Medium before Low; callers do not
  select an alternate direction.
- Completed is terminal in this workflow; reopening and direct completion from
  Pending are not supported.
- A single application instance owns the local JSON store and serializes
  mutations. Concurrent writers from independent application processes are
  outside this academic feature's scope.
- The local JSON store's path is an environment/deployment choice and is not
  exposed through the API.

## Change History

| Version | Date | Change |
|---|---|---|
| 1.3.0 | 2026-11-12 | **Proposed; pending human review.** Clarify submitted versus authoritative harness artifacts, exact-digest verification and D-01 blocking, add the controlled instruction-file inventory, separate Bandit execution from human disposition, and update AC/NFR traceability without changing the existing requirement or acceptance-criterion counts. |
| 1.2.2 | 2026-11-11 | **Proposed; pending human review.** Specify the exact error-detail schema, empty-array behavior, deterministic ordering, OpenAPI shape, and updated traceability/success criteria. |
| 1.2.1 | 2026-11-11 | Made malformed-store request-time validation explicit; aligned sequential determinism, concurrent serialization, ID assignment, persistence rollback, acceptance criteria, test mappings, and success criteria. |
| 1.2.0 | 2026-11-11 | Clarified in-process concurrent mutation serialization and malformed-store runtime behavior; added or updated acceptance, test, and success-criteria coverage. |
| 1.1.0 | 2026-11-11 | Added PATCH malformed-JSON statuses, persisted-record validation, repository hygiene/security review, protected harness baselines, separated human decision gates, and updated traceability. |
| 1.0.0 | 2026-11-11 | Initial feature specification draft. |
