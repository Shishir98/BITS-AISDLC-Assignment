# Data Model and State Handling

This design artifact translates the approved-for-planning feature specification
into application data boundaries. It does not introduce additional API fields or
task features.

## Task

| Field | Type and invariant |
|---|---|
| `id` | Positive integer; Boolean values are invalid. Unique and assigned from the persisted `next_id`. |
| `title` | Trimmed string, 1-200 characters. |
| `description` | Null or string, 0-2,000 characters. |
| `tags` | At most 20 distinct, trimmed, lowercase strings of 1-32 characters, in lexicographic order. |
| `priority` | `Low`, `Medium`, or `High`. |
| `status` | `Pending`, `In Progress`, or `Completed`. |

The task data model uses Pydantic validation with strict integer handling and
rejects unknown fields. Request schemas remain separate from stored/domain
models so API-specific partial-update semantics do not leak into persistence.

## Persisted Document

The root JSON object has exactly `next_id` and `tasks`. `next_id` is a positive
integer (not a Boolean) greater than every stored task ID. Each task object has
exactly the six fields in the Task table. Duplicate JSON object member names,
unknown or missing fields, invalid types or values, duplicate IDs, and invalid
counter relationships are malformed stored data.

The JSON decoder must detect duplicate member names before converting objects
to ordinary dictionaries (for example, through an `object_pairs_hook`), then
validate the complete document with strict models.

A missing file represents an empty collection with `next_id` equal to 1. The
application process must not read the file during startup. The first request
that accesses storage causes the repository to load and validate it. A malformed
document raises `MalformedStoredDataError` with code
`malformed_stored_data`; it is never repaired or replaced automatically.

## Status Lifecycle

New tasks begin as `Pending`. State-changing transitions are only
`Pending -> In Progress` and `In Progress -> Completed`. Requesting the current
status is an idempotent no-op; all other transitions between different statuses
are rejected. `Completed` is terminal.

## Ownership and Dependencies

- API request/response schemas belong to the API layer.
- Task rules and transitions belong to the business logic layer.
- Persisted-document parsing, validation, serialization, and file operations
  belong to the JSON repository.
- API routes call business logic; business logic uses the repository boundary.
  Neither routes nor business logic access JSON files directly.
- The application factory wires dependencies without loading the store. A
  request-triggered repository load preserves the specified successful startup
  behavior when the existing file is malformed.

## Mutation and Persistence Commit

One in-process synchronization primitive protects every mutation from reading
the current state through persistence and in-memory commit. Readers take a
consistent snapshot under the same coordination boundary. Concurrent mutation
results must correspond to some serial execution; the request-to-ID assignment
within that execution is unspecified.

For a mutation, construct and serialize the complete candidate document before
changing the primary store or live in-memory state. For an existing store,
preserve its exact bytes in a uniquely named same-directory backup, close that
file, and verify its bytes before attempting replacement. Write and close the
candidate in a uniquely named same-directory temporary file. Use the existing
`os.replace` operation as a best-effort replacement mechanism; then read the
primary back and verify the exact candidate bytes before advancing the
in-memory snapshot.

On an application-handled persistence failure, attempt to restore the previous
bytes from the verified backup using a same-directory temporary file and verify
the restored primary byte-for-byte. If the original store was absent, remove a
partially installed primary and verify that the path is absent. In-memory state
remains unchanged after failed persistence. If recovery cannot be verified,
preserve the backup, mark the repository as requiring recovery, and fail closed
to normal mutations. Temporary and backup files may be cleaned after a
successful, verified transaction; cleanup failure does not invalidate that
commit. The repository returns distinct typed errors for malformed stored
content and local persistence failures.

The application factory accepts an optional explicit `Path`; when absent, a
non-empty `SMART_TODO_STORE_PATH` is used, otherwise the default is
`data/tasks.json`. Relative paths are resolved against the process working
directory at app creation. App creation does not access the store. The default
`data/` directory is excluded from Git; any custom path must also be outside
tracked files or ignored.

The contract applies only to application-handled failures. It does NOT guarantee
OS-level atomic visibility during Windows replacement, crash durability across
sudden power loss, recovery after abrupt process termination or OS failure
during replacement, or hardware-level persistence beyond documented
application operations. The approved v1.4.0 amendment resolves D-05 without
claiming these unsupported platform guarantees.

## Approved Error Detail Contract (Specification v1.3.0)

The approved v1.3.0 specification defines each `error.details` item
as an object with exactly three required string fields: `field`, `code`, and
`message`. Errors without field-level information use `[]`. Sort details
ascending by field path, then by `code` and `message` for ties. This model is
approved on 2026-11-12; it does not add fields to the task model or change the
existing error envelope/codes.
