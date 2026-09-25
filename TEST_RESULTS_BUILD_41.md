# Build 41 verification record

Date: 2026-09-25. Status: **staging candidate; milestone acceptance pending**.
No tests performed by the user on Build 40 are counted as Build 41 verification.

## Executed and passed

| Check | Actual result | Evidence |
|---|---|---|
| Full portable verification | 147 Python tests passed; Admin and Android source checks passed | `verification/build41-portable-tests.txt` |
| PostgreSQL SQL parser + regression exercise | Both migrations and constant operations SQL parsed; 210 distinct domain SQL statements parsed while 147 SQLite tests passed | `verification/build41-postgres-syntax.txt` |
| Real Gunicorn HTTP smoke | Two workers; health/Admin CSP; passenger sign-in; authenticated profile; persisted session after process restart | `verification/build41-gunicorn-smoke.txt` |
| Python compileall | Exit 0 | `verification/build41-python-syntax.txt` (empty means no diagnostics) |
| Deployment/workflow YAML syntax | All three YAML files parsed | `verification/build41-config-syntax.txt` |

Portable coverage retains the prior ride/quote/route/GST, dispatch/radar, decline,
expiry, retries, earnings, sessions, staff RBAC and support regressions. New tests
cover staging configuration rejection, hidden development OTP, invitation checks,
disabled development endpoints, Host/Origin/HTTPS guards, rate-limit failures,
readiness behavior, oversized-body rejection and Compliance overview filtering.
Admin checks exercise Compliance's paginator without issuing a forbidden request.

The PostgreSQL parser is **not a PostgreSQL server**. SQLite tests plus SQL parsing
cannot establish PostgreSQL type conversion, execution, process locking, migration,
backup or restore correctness. The real HTTP smoke used SQLite, not PostgreSQL.

## Attempted but blocked / not executed

| Gate | Status / precise reason |
|---|---|
| Passenger/Driver Gradle debug + staging | Attempted; Gradle distribution download failed with `Network is unreachable`. Logs: `build41-passenger-gradle.txt`, `build41-driver-gradle.txt`. No APK compiled here. |
| Actual PostgreSQL integration | No usable PostgreSQL server/container runtime in this workspace. System package installation lacked required permissions. Supplied `postgres-integration.py` and CI job have not been executed against a real engine. |
| SQLite-to-PostgreSQL content migration | Importer implemented; real-engine round-trip remains part of the blocked PostgreSQL suite. No user database was migrated. |
| PostgreSQL backup/restore | Tools and destructive disposable-target CI drill implemented; no live restore drill executed here. |
| Render Blueprint/service deployment | Not run; account access and explicit owner approval of resources/costs are required. |
| CI/CD jobs, protected environments, rollback | Workflow/configuration implemented; not installed/executed in an owner repository/account. |
| Managed backups, off-host export schedule, alert delivery | Runbooks/probes/tools supplied; actual account configuration and verification remain. |
| Browser rendering / Android physical devices | Build 41 staging screens and separate-network trip lifecycle not tested on devices here. Source checks are not rendering or compilation. |
| Production security/load/compliance approval | Not claimed; future roadmap gates remain. |

Package CRC, file inventory and exclusion checks are recorded in
`verification/build41-package-check.txt`. Historical results under `docs/history/`
describe earlier builds, not this candidate.

## Findings fixed during verification

- PostgreSQL reserved identifier in rate-limit migration.
- Gunicorn logging dictionary prevented HTTP server startup.
- PostgreSQL AVG returns Decimal; rating JSON is now explicitly numeric.
- Driver debug-only gates would have bypassed staging login/backend/GPS.
- Compliance overview leaked ride summaries and its page fetched a forbidden ride list.
- Imported Driver credentials must retain their rows while rotating secret hashes;
  deleting rows would have prevented later password sign-in from storing a token.

Completion requires green PostgreSQL and Android jobs, reviewed migration/restore
evidence, authorized deployment and the integrated manual checklist. Do not use
this record as evidence of public-launch readiness.
