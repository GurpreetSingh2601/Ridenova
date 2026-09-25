# Build 41 known issues and acceptance gates

| Priority | Item | Required resolution |
|---|---|---|
| Blocker | PostgreSQL engine tests not executed here | Run supplied disposable-DB CI suite; fix any execution/type/concurrency/import/restore failures before deployment |
| Blocker | New Android variants not compiled here | Gradle dependency download blocked by workspace network; compile both debug/staging variants in CI or Android Studio |
| Blocker | Render not deployed | Owner approves exact services/costs/region, then authorized setup and smoke tests |
| Blocker | Hosted cross-network functionality untested | Complete one integrated device checklist after deployment |
| Required setup | Managed backups, off-host retention, external alerts | Configure approved services, perform restore drill and verify alert delivery |
| Required setup | CI/CD and rollback exercise | Connect owner-controlled repository, require checks/environment approval, record a verified deployment/rollback |
| Limitation | Test-only passenger invitation codes | No real SMS/phone ownership verification; protect code distribution, rotate on removal, never use for public registration |
| Limitation | Driver signup/recovery disabled in staging | Provision invited test accounts through private CLI; resolve legacy/recovery accounts before migration |
| Limitation | Global DB request lock; ride JSON scans | Controlled small-scale staging only; normalize hot data paths and measure capacity before beta |
| Limitation | Minimal Render DB plan, no HA | Reassess measured usage, concurrency and recovery objectives before widening testing |
| Limitation | Oregon region | US data residency; do not assume Canadian-only storage or compliance approval |
| Deferred | Real money, push/SMS, launch compliance | Follow Builds 42–50; do not enable real charges/payouts |

This candidate is not labelled a completed Build 41. Current scripts/SQL passing
syntax or SQLite tests is not evidence that PostgreSQL execution/restore passed.

Build 40 historical docs are retained for context. `fleet28/29/30/33/35.py`,
`experience34.py` and `staff38.py` names identify additive implementation lineage,
not the active release version; they are not duplicate backends.
