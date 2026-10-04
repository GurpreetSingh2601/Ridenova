# PostgreSQL execution record

Earlier in this Build 43 task, the actual PostgreSQL 16.10 suite executed against two disposable UTF-8 databases:

```
Ran 23 tests in 9.229s
OK
```

It included the 12 existing persistence/migration/finance/dispatch tests and 11 Build 43 tests: quote-bound notes, legacy defaults, server timer/retry, stale/far GPS, legacy arrival verification, restart/idempotency, ownership/stage restrictions, start/no-show race, authenticated HTTP endpoints, rebooking and passenger-cancel race. Independent-process assignment and backup/restore refusal/checksum tests also passed.

The runtime was subsequently replaced and the temporary raw log was lost. This is a transcription of the observed executed result, not a newly generated test log. A repeat in the replacement runtime could not start PostgreSQL because it provides only a mapped root UID and disallows switching to the unprivileged database user. Its failure output is preserved separately in build43-postgres-rerun-blocked.txt; it is not a passing repeat. After that run, no-show reason type validation was hardened to reject non-string JSON values as HTTP 400 instead of a type error. This change and the final backend source passed the SQLite/HTTP suite; PostgreSQL SQL, schema and transaction behavior are unchanged. CI runs these same tests with a PostgreSQL service.
