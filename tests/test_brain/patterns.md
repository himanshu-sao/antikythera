

## Learned on 2026-05-23 17:09:36

## Development Lifecycle
- **Pattern**: A strictly sequential multi-agent workflow: `refiner` (generates `spec.md`) $\rightarrow$ `architect` (generates `architecture.md`) $\rightarrow$ `tester` (generates `tests.md`) $\rightarrow$ `executor` (generates `execution_report.md`).
- **Context**: When evolving a high-level idea from a one-liner into a fully implemented and verified feature.

## File Organization
- **Pattern**: Use of a dedicated directory per idea following the structure `requirements/[ID]/[file_type].md` (e.g., `requirements/ID-01/spec.md`).
- **Context**: To maintain isolation, traceability, and organized context for multiple concurrent or sequential ideas.

## Architectural Design
- **Pattern**: Utilization of Mermaid diagrams for visual representation in `architecture.md` and mandatory ingestion of `brain/patterns.md` as a design input.
- **Context**: When the `architect` agent is generating technical designs to ensure both visual clarity and adherence to established system patterns.

## Test-Driven Execution
- **Pattern**: The `tester` generates `tests.md` based on the intersection of `spec.md` and `architecture.md`, which the `executor` must then use to verify the implementation.
- **Context**: During the `EXECUTING` stage to ensure the final implementation is grounded in pre-defined requirements and architectural constraints.