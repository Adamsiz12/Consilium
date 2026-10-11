# Research handoff report template

Do not default to a successful status. Supply evidence or explicitly record an unknown value for every applicable field.

| Section | Required information |
|---|---|
| Identity | Plan version, code version, source digest, environment, date |
| Last verified checkpoint | Phase, revision, test command, result, review evidence |
| Current state | Current phase, completed work, unfinished work, blockers |
| Partial implementation | Changed files, reasons, what ran and what did not |
| File relationships | Inputs, outputs, dependencies, responsibilities of important modules |
| Tests | Passes, failures, unrun checks, impact on prior tests |
| Decisions | Accepted/rejected decision, reason, limitations |
| Requirements | Thirty-requirement mapping to implementation, tests, and evidence; no guessed percentages |
| Recovery | Last valid state, pending operations, unresolved uncertainty |
| Next action | First authorized task, files, command, expected outcome |
| Reproduction | Environment setup, locked dependencies, permitted fixtures, test commands |
| Limitations | Missing real access, incomplete data, unproven behavior |
| Transfer security | File allowlist and checks for passwords, keys, and login sessions |

Retain the source and unfinished snapshot with its evidence. A prose report is not the only storage location for application state.

Record subtle behavior in `resume.known_quirks` with reasons and code/test/decision references. The latest run may have failed: distinguish it from previous acceptance. If a newer run is unexecuted or still active, do not describe an older result as certain current verification. Refresh derived views after canonical inputs change.

Locating the first task within ten minutes is a future measurement target, not an already measured guarantee. New reports use English labels; preserve original quotations and historical evidence.
