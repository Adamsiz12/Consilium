# Automated native Windows and Linux checks

The assistant owns authorized Windows setup, execution, artifact retrieval, and troubleshooting. Do not assign those duties to the user. The public repository publication has explicit standing authorization; offline checks need no model keys or login secrets.

## Historical baseline

Workflow 37446806486 verified commit 1f8191cac322f15e6118cf62b8f0c6f5b636595a. Its 222 packaged files were compared to Git blobs, and both host/matrix reports and ZIP hashes were verified. Windows used windows-2025/Python 3.12.10; Linux used ubuntu-24.04/Python 3.12.14. Each recorded sixty foundation tests, seventy-eight control tests, and four CLI scenarios at that source.

References include `evidence/automation/CI_PUBLICATION.json` and CI_JOBS_FINAL. P01's separate recorded review accepted that historical source; these counts and receipts do not certify newer implementation.

## Current workflow

`.github/workflows/check.yml` runs native Windows/Linux jobs and the matrix validator, with a separate dependency audit. Mutable target outputs are refreshed while historical/accepted snapshots remain intact. Host outputs are separate; text is UTF-8 and dependencies are pinned. Native execution also includes current persistence and other development suites. Use `evidence/targets/TARGET/LATEST.json` and verify source digests and report graphs.

The matrix runs `tools/run_current_phase.py` for the first unfinished phase and registered regressions, with combined-phase-evidence outputs. It does not accept the phase; criterion-based review/gating remains separate.

Workflow permissions are read-only. Native/matrix jobs are bounded at twenty minutes; the audit at ten. Remote artifacts have thirty-day retention. Retrieve and verify them before expiration. Missing downloads block evidence reconciliation; after a retrieval failure, continue diagnosis without claiming verified host results.

P08 has no registered executable acceptance checks and remains blocked even when native code checks pass. Read exact current statuses from PROGRESS.json, VALIDATION_REPORT.json, and actual workflow results rather than old publication checkpoints.

Preserve all thirty requirements and seventeen phases. Same-author review is not independent. These workflows make no paid or live provider-generation calls. Passing or queued CI does not waive live prerequisites or advance P08.
