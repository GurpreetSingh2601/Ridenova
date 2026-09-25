# Build 41 staff permissions and testing

The backend is authoritative. The Admin portal exposes workspaces appropriate to the signed-in role, and every request is independently authorized server-side.

| Workspace / capability | Owner | Operations | Support | Finance | Compliance |
|---|---:|---:|---:|---:|---:|
| Dashboard | Yes | Yes | Yes | Yes | Yes |
| Simulator ride transitions | Development only | Development only | No | No | No |
| Ride summaries / timelines | Read | Read | Read | Read | No |
| Drivers / Fleet | Full | Full | No | No | Documents/review only |
| Finance | Yes | No | No | Yes | No |
| Support / feedback | Yes | Yes | Yes | No | No |
| Staff & Access | Yes | No | No | No | No |
| Audit Logs | Yes | No | No | No | Read |

- Only Owner can create, enable or disable staff accounts.
- Staff cannot disable themselves; the final active Owner cannot be disabled.
- Disabling an account revokes sessions. Sign-out revokes the current session.
- Passwords are salted PBKDF2 hashes; Build 41 ships no default credentials.
- Ride summary APIs omit passenger phone/PIN, but include pickup/destination addresses and driver names for every role with ride.read, including Finance. Do not assume Finance receives address-redacted records. Finance totals/ledger are returned only to Owner/Finance.
- Compliance cannot activate/suspend drivers or edit ride eligibility. Its overview does not contain ride lists; aggregate dashboard counts remain available to all roles.
- The legacy development Admin token is disabled in staging even when no Owner exists. Staff accounts are required there.

## Actual endpoint/action matrix

| Endpoint / action | Required permission | Roles |
|---|---|---|
| GET `/v1/admin/overview` | overview; response fields filtered | All staff; ledger/totals Owner/Finance, fleet Owner/Operations/Compliance, rides all except Compliance |
| GET `/v1/admin/rides`, `/v1/admin/rides/{id}/events` | ride.read | Owner, Operations, Support, Finance |
| POST ride transition / driver-position simulator | ride.write AND development environment | Owner, Operations; always denied in staging |
| GET `/v2/fleet/admin/drivers`, driver audit | fleet.read | Owner, Operations, Compliance |
| POST driver status, eligibility, reset-token | fleet.write | Owner, Operations |
| GET driver documents/content | documents.read | Owner, Operations, Compliance |
| POST document review | documents.write | Owner, Operations, Compliance |
| GET `/v1/admin/support-cases`, `/feedback` | support.read | Owner, Operations, Support |
| POST support case status | support.write | Owner, Operations, Support |
| GET `/v1/staff/accounts` | staff.read | Owner |
| POST `/v1/staff/accounts`, account status | staff.write | Owner |
| GET `/v1/staff/audit` | audit.read | Owner, Compliance |
| GET `/v1/staff/me`, POST logout | authenticated staff | All active staff |

Role sets come from `staff38.PERMS`; routing checks come from `server.make_handler`.
Tokens are held in the Admin page's memory and expire after eight hours; refresh
tokens are not implemented for staff. Closing/reloading the page requires sign-in.
Staging rate limits are enforced in the shared database, not just the UI.
The token reset endpoint remains authorized for operational compatibility, but
development recovery is disabled in staging. Resolve recovery through a controlled
administrative procedure; do not distribute simulator recovery tokens as staging login.

## Local development Owner bootstrap

On first launch of a database with no staff, set a unique username and password of at least 14 characters:

```powershell
$env:RIDENOVA_OWNER_USERNAME="owner-name"
$env:RIDENOVA_OWNER_PASSWORD="use-a-long-unique-secret"
$env:RIDENOVA_DEV_ADMIN_TOKEN="another-private-development-secret"
python START_SERVER.py --database "G:\RideNova\data\ridenova.sqlite3"
```

After the first Owner exists, remove `RIDENOVA_OWNER_PASSWORD`. Never commit it. Existing staff databases are preserved and are not bootstrapped again.

For staging, use `python tools/bootstrap.py owner` from `Passenger/backend` in a
private shell with DATABASE_URL set. It prompts for credentials, requires an empty
staff table and never grants a default Owner. Imported Owner accounts are preserved.

## Acceptance checks

1. Sign in as Owner; verify every implemented workspace appears and loads.
2. Create one temporary account for each restricted role and verify only the table above is visible.
3. Request a forbidden endpoint with each restricted session and confirm HTTP 403.
4. Expire/disable an account; confirm HTTP 401 returns the UI to sign-in without cached data.
5. Confirm the Owner cannot self-disable or disable the final active Owner.
6. Perform staff/Admin actions and confirm Audit Logs records them.
7. Sign out and confirm the old token is rejected.

Automated coverage includes bootstrap, creation, RBAC, finance redaction, session revocation, last-owner protection, pagination and audit. Browser rendering still requires manual acceptance.
