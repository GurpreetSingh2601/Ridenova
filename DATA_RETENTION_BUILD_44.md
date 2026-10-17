# Build 44 data inventory and retention

The durations below are implemented engineering defaults, not certified legal retention periods. Privacy, provider licensing and compliance review are required before launch. All records use the existing shared database. History begins with Build 44; missing earlier GPS is not fabricated. Backups require their own access/deletion policy.

| Data | Retention / access |
|---|---|
| Actual driver trip GPS, accuracy, observation/receipt timestamps | 30 days; active trips or documented holds protect it. Owner/Operations/Support only; no off-trip trail. |
| Optional passenger GPS | Same default; explicit per-trip consent and foreground screen. Revocation deletes it even under a hold. |
| New navigation route snapshots / versions | Configured 30-day cache cap, even under a hold. Actual driver GPS remains the investigation record. |
| New trip/check-in/reassignment narrative | 365 days unless active/held. Existing legacy events retain their previous lifecycle. |
| Share token hashes | Four hours maximum; revoke/end disables immediately; cleanup removes expired hashes. Public subset is destination and driver position only. |
| Document revision bytes/review metadata | 365 days unless current assigned driver is protected by an active/held trip; current documents remain. Owner/Operations/Compliance, audited access. |
| Driver inbox | 90 days; own driver only. |
| Holds | Explicit reason, actor and 0–90 days per action. Owner/Operations only; renewable by explicit audited action. No extension to configured route cache cap. |
| Financial/account/support records | Preserved; no new deletion or recalculation of accepted fares/ledger in this release. |

Existing scheduler runs maintenance about once per minute. Inbox requests also check reminders. There is no guaranteed offline push/SMS/email in this build.

Driver queue: 900 samples/24 hours, original trip and credential, cleared on logout/credential change, excluded from Android backups. Accurate delayed samples can complete the historical trail but never refresh live availability. Gaps, stale timestamps and accuracy remain visible. GPS is not tamper-proof evidence of misconduct.

Existing Build 43 quote/trip payloads can retain provider-derived routes/addresses. Full legacy provider-data retention migration, backup retention and privacy/legal review remain launch gates. Historical accounting/customer-entered data is not silently erased. Public Maps policy references: https://developers.google.com/maps/documentation/routes/policies and https://cloud.google.com/maps-platform/terms/maps-service-terms .
