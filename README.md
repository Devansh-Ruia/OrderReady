# OrderReady

OrderReady is a planned intake assistant for a solo custom T-shirt printing founder. The founder receives informal customer messages and must turn incomplete or conflicting details into a usable intake ticket without inventing information. Reconstructing garment colors, size quantities, and deadlines is the operational bottleneck.

The project is intended for Chatathon 2026 in the Misneach track.

## Prototype status

[Certain] Repository inspection found only this README and Git metadata. The working prototype has not yet been implemented.

| Essential capability | Implemented code | Runtime verified | Mocked behavior | Planned work |
| --- | --- | --- | --- | --- |
| Extract inquiry into an editable form | None | No | None | Propose supplied values and leave uncertainties unresolved |
| Validate required fields and quantities | None | No | None | Check missing fields and quantity inconsistencies deterministically |
| Export a reviewed intake ticket | None | No | None | Allow export only after human review and successful validation |

## Planned workflow and scope

Paste inquiry → extract supplied details → review missing or conflicting information → founder corrects or confirms → export checked intake ticket.

The MVP is limited to one shirt style, sizes S/M/L, and one print location. The fixed shirt style and print location have not been configured. Their values must be explicitly configured, never invented.

The intake fields are color, requested total, size quantities for S/M/L, and requested deadline. The review screen should retain the original inquiry alongside editable proposed values, missing-field notices, and quantity discrepancies. Omitted values must remain unresolved rather than becoming defaults.

Deterministic validation should compare the requested total with the sum of size quantities. Missing required information, ambiguous deadlines, and unresolved contradictions must prevent completed status and export. Every founder edit must trigger validation again before completion is possible.

The planned output is an inspectable intake ticket containing the reviewed fields, requested total, size breakdown, computed size total, and requested deadline. It is not a quote, a production-ready order, or a promise that the deadline can be met.

Pricing, artwork review, inventory, payments, messaging integrations, automatic customer outreach, and production management are excluded.

## AI and deterministic code

AI is intended to interpret messy language and propose structured field values. Missing or ambiguous details must remain unresolved. A model response is a proposal, not the authority on completeness.

Deterministic code must own required-field validation, quantity arithmetic, readiness state, and export eligibility. The founder must review the proposed fields, and human edits must pass validation before export.

No provider, model, or AI configuration exists in the repository. Manual entry as a fallback is also unimplemented. If added later, it must be labeled manual mode when model access fails. Hardcoded or replayed responses must be identified as simulated output, never live model output.

## Local setup

There is no runnable application or selected implementation stack in the repository.

| Setup item | Current repository evidence |
| --- | --- |
| Prerequisites | No application runtime or dependency requirements declared |
| Installation command | None defined, no dependency manifest |
| Run command | None defined, no application entry point |
| Required environment variables | None defined by application code or configuration |
| Environment template | None present |

There are no application setup steps to run yet.

## Planned demo

Both inquiries below are synthetic. These walkthroughs have not been executed. No external service integration or simulated external behavior exists in the repository.

### Normal case

"Thirty navy shirts. Ten small, ten medium, ten large. Needed September 28, 2026."

Once the fixed shirt style and print location are configured, extraction should propose navy, a requested total of 30, S/M/L quantities of 10/10/10, and September 28, 2026. The founder reviews the form. Validation should confirm that the size quantities sum to 30 and all required fields are resolved before permitting completed status and export.

### Contradiction case

"Thirty navy shirts. Ten small, ten medium, five large. Needed September 28."

The requested total is 30, but the supplied size quantities sum to 25. The application should preserve both values, flag the discrepancy, and require a human decision. Silently changing five large to ten large is a failure.

The deadline also lacks a year. No date-resolution policy exists, so the year must remain unresolved until the founder clarifies it. The application must not infer a year from the hackathon or current date.

For a synthetic correction, the founder could explicitly confirm a requested total of 25 and a deadline of September 28, 2026. The application should preserve S/M/L quantities of 10/10/5 and validate again. Completed status and export should become available only after all required information, configured scope, and human review pass the checks.

## Validation and evidence

### Observed results

The repository file listing and `git ls-files` showed only README.md outside Git metadata. No tests, test configuration, or test command exist. No application tests or demo cases were run, and no runtime behavior was verified.

The proposed success metric is synthetic acceptance-case pass rate, currently **not yet measured**. A case passes only when the application correctly accepts, blocks, or requests clarification according to the expected result without inventing missing details. Report X/N only after executing those cases.

### Planned acceptance criteria

| Case | Expected result |
| --- | --- |
| Complete normal inquiry | Accept only after founder review and successful validation |
| Missing required field | Request clarification and block completion and export |
| Requested total 30 with size sum 25 | Preserve both values, flag the discrepancy, and block completion and export |
| Deadline without a year | Keep the year unresolved and request clarification |
| Founder correction | Revalidate all required fields and arithmetic before permitting completion and export |
| Unconfigured shirt style or print location | Require explicit configuration without inventing values |
| Request outside the supported format | Flag the unsupported details for human review without silently converting them |

There is no measured evidence of extraction accuracy, time savings, revenue gains, user validation, or market uniqueness.

## Limitations and data handling

The planned format supports only the scoped shirt style, S/M/L sizes, and one print location. Extraction can be uncertain even when a message appears complete, so human review is required. Intake validation does not establish production feasibility or deadline availability.

No application code establishes transmission, storage, or retention behavior. Provider data handling and application persistence remain undecided. No claims about local-only processing, encryption, or non-retention have been verified. Use synthetic inquiries for the planned demo.

## Hackathon build window

The intended Chatathon 2026 Misneach build window is three hours. Allocate 150 minutes to features and reserve the final 30 minutes for integration, testing, repository freeze, and submission. This is a planned schedule, not evidence of completed work.
