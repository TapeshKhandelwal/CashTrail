# API documentation

CashTrail's backend is a JSON REST API (Django REST Framework).

- **Swagger UI:** `/api/docs/` lists every endpoint with its request and response fields, filters and error responses, and can call the API directly.
- **OpenAPI 3 schema:** `/api/schema/`.
- **Base URL (local):** `http://localhost:8000/api`. Every path ends in `/`, except the `reports/*.csv` paths.

## Authentication

JSON Web Tokens.

| Step | Request | Result |
|---|---|---|
| Sign in | `POST /api/auth/login/` with `{"username", "password"}` | `access` and `refresh` tokens and the user (role, branch) |
| Call the API | header `Authorization: Bearer <access>` | the access token lasts 30 minutes |
| Refresh | `POST /api/auth/refresh/` with `{"refresh"}` | a new token pair; the old refresh token stops working |
| Sign out | `POST /api/auth/logout/` with `{"refresh"}` | the refresh token is revoked |
| Who am I | `GET /api/auth/me/` | the signed-in user |

Login is rate-limited per IP and per username. Deactivating a user, resetting their password or changing their role or branch signs them out.

The web app never handles tokens in the browser: its Next.js server signs in on the user's behalf, keeps the tokens in httpOnly cookies and forwards API calls.

## Roles and access

| Role | Can see |
|---|---|
| `ADMIN`, `FINANCE` | every branch |
| `BRANCH_MANAGER` | their own branch |
| `AGENT` | their assigned customers and those customers' loans, their own receipts, hand-overs and UPI requests |

A role that may not use an endpoint gets `403`. A record outside what the caller can see returns `404`, so its existence is not revealed.

## Conventions

- **Money** is a string with two decimals, such as `"48500.00"`, in requests and responses. A JSON number with a fraction (`2000.5`) is rejected.
- **Dates and times** are ISO 8601 in Asia/Kolkata; date filters (`date_from`, `date_to`) are inclusive `YYYY-MM-DD`.
- **Lists** are paginated: `?page=2&page_size=50` (max 100) returns `{count, next, previous, results}`. They accept filters as query parameters, `search=` and `ordering=` (e.g. `-collected_at`).
- **Cash counts** map a note value to a count, e.g. `{"500": 3, "100": 5}`, and must add up to the amount they describe.
- Every response carries an `X-Request-ID`, which also appears in the server log and the audit trail.

## Idempotency

Creating a receipt, a hand-over, a bank deposit, a gateway settlement or a UPI request requires an `Idempotency-Key` header with a UUID:

- retry with the same key and body → `200` with the original record and `Idempotent-Replayed: true`, nothing created twice;
- same key, different body → `422 IDEMPOTENCY_CONFLICT`;
- missing key → `400 IDEMPOTENCY_KEY_REQUIRED`.

## Errors

Every error has the same shape:

```json
{ "error": { "code": "OVER_COLLECTION", "message": "The amount exceeds the outstanding balance.", "details": { "outstanding": "41447.00", "amount": "50000.00" } } }
```

| Status | Common codes |
|---|---|
| 400 | `VALIDATION_ERROR` (field errors in `details`), `IDEMPOTENCY_KEY_REQUIRED` |
| 401 | `NOT_AUTHENTICATED`, `TOKEN_NOT_VALID`, `NO_ACTIVE_ACCOUNT` |
| 403 | `PERMISSION_DENIED`, `SCOPE_VIOLATION`, `SEGREGATION_OF_DUTIES` |
| 404 | `NOT_FOUND` |
| 409 | `POSSIBLE_DUPLICATE`, `DUPLICATE_BANK_REFERENCE`, `PENDING_SUBMISSION_EXISTS`, `INVALID_STATE_TRANSITION`, `RECORD_LOCKED` |
| 422 | `VALIDATION_FAILED` (business rule), `OVER_COLLECTION`, `DENOMINATION_MISMATCH`, `IDEMPOTENCY_CONFLICT` |
| 429 | `THROTTLED` (with `Retry-After`) |
| 502 | `GATEWAY_ERROR` (payment gateway unreachable) |

## Endpoints

Roles: **Adm** admin, **Fin** finance, **Mgr** branch manager, **Agt** agent, **All** any signed-in user. **(key)** needs an `Idempotency-Key`.

### Users and branches

| Method | Path | Roles | Purpose |
|---|---|---|---|
| GET, POST | `/api/users/` | Adm (read: Fin, Mgr) | List or create users |
| PATCH | `/api/users/{id}/` | Adm | Update a user's details, role or branch |
| POST | `/api/users/{id}/deactivate/`, `…/activate/`, `…/set-password/` | Adm | Deactivate, reactivate, reset the password |
| GET, POST | `/api/branches/` | All (create: Adm) | List or create branches |
| PATCH | `/api/branches/{id}/` | Adm | Update or deactivate a branch |

### Customers and loans

| Method | Path | Roles | Purpose |
|---|---|---|---|
| GET, POST | `/api/customers/` | All (create: Adm, Mgr) | Customers with outstanding and overdue amounts |
| GET, PATCH | `/api/customers/{id}/` | All (edit: Adm, Mgr) | Customer detail; edit contact details or deactivate |
| POST | `/api/customers/{id}/assign/` | Adm, Mgr | Assign the customer to an agent of the branch |
| GET | `/api/agent/customers/` | Agt | The agent's assigned customers, overdue first |
| GET, POST | `/api/loans/` | All (create: Adm, Mgr) | Loans with paid, outstanding and overdue amounts; create a loan and its EMI schedule |
| GET, PATCH | `/api/loans/{id}/` | All (edit: Adm, Mgr) | Loan detail; correct the terms before the first repayment |
| GET | `/api/loans/{id}/schedule/` | All | Repayment schedule |
| GET | `/api/loans/{id}/repayments/` | All | Repayment history |
| GET | `/api/loans/schedule-preview/` | Adm, Mgr | Preview a schedule without saving |

### Collections (agents)

| Method | Path | Roles | Purpose |
|---|---|---|---|
| POST | `/api/collections/` **(key)** | Agt | Record a cash repayment (`loan_id`, `amount`, optional `remarks`); partial payments allowed; applied to the oldest unpaid instalment first |
| GET | `/api/collections/` | All | Receipts, filterable by date, branch, agent, status and mode |
| GET | `/api/collections/{id}/` | All | Receipt with its allocations, balance after and lifecycle |
| GET | `/api/collections/daily-summary/` | All | One day's collections and the cash still with agents |
| POST | `/api/collections/{id}/void/` | Agt | Cancel your own receipt before hand-over, with a reason |

### Branch reconciliation

| Method | Path | Roles | Purpose |
|---|---|---|---|
| POST | `/api/submissions/` **(key)** | Agt | Hand receipts over to the branch (`collection_ids`, `declared_amount`, optional note count) |
| GET | `/api/submissions/`, `/api/submissions/{id}/` | All | Hand-overs with their receipts and discrepancies |
| POST | `/api/submissions/{id}/approve/` | Adm, Mgr | Record the cash counted (`received_amount`, optional note count); a difference needs `reason_code` and `remarks` and opens a discrepancy |
| POST | `/api/submissions/{id}/reject/` | Adm, Mgr | Reject with a `reason`; the receipts go back to the agent |
| GET, POST | `/api/discrepancies/` | All (raise: Adm, Mgr, Fin) | List or raise discrepancies |
| POST | `/api/discrepancies/{id}/resolve/` | Adm, Mgr, Fin | Resolve or write off, with notes |
| GET | `/api/reconciliation/branch-summary/` | Adm, Fin, Mgr | Branch summary: expected, collected, received, deposited, settled, open discrepancies |
| GET | `/api/reconciliation/agents-summary/` | All (agents: themselves) | Per-agent collections, hand-overs and cash in hand |

### Bank deposits and settlement

| Method | Path | Roles | Purpose |
|---|---|---|---|
| GET | `/api/deposits/pending-cash/` | Adm, Mgr | Approved cash not yet deposited |
| POST | `/api/deposits/` **(key)** | Adm, Mgr | Deposit approved cash: bank account, amount, date and slip reference (unique per account) |
| GET | `/api/deposits/`, `/api/deposits/{id}/` | Adm, Fin, Mgr | Deposits with settlement status; `?delayed=true` lists those past the SLA |
| POST | `/api/deposits/{id}/settle/` | Adm, Fin | Confirm the credit from the bank statement; a difference opens a discrepancy |
| POST | `/api/deposits/{id}/fail/` | Adm, Fin | Mark a deposit failed; its cash returns to the branch |
| GET, POST | `/api/bank-accounts/` | Adm, Fin, Mgr (create: Adm) | Company bank accounts |
| GET, POST | `/api/gateway-settlements/` **(key)** | Adm, Fin | Record a UPI gateway payout (gross, fee, tax, net, UTR) |
| GET | `/api/gateway-settlements/pending/` | Adm, Fin | UPI payments not yet settled |

### UPI payments (optional gateway)

| Method | Path | Roles | Purpose |
|---|---|---|---|
| GET | `/api/payments/config/` | All | Which gateway is active |
| POST | `/api/payments/orders/` **(key)** | Agt | Raise a UPI payment request for a loan |
| GET | `/api/payments/orders/`, `/api/payments/orders/{id}/` | All | Payment requests and their status |
| POST | `/api/payments/orders/{id}/refresh/` | All | Ask the gateway whether the customer has paid, and issue the receipt if so |
| POST | `/api/payments/verify/` | Agt | Confirm a Razorpay checkout by its signature |
| POST | `/api/payments/webhooks/cashfree/`, `…/razorpay/` | Gateway (signed) | Payment notifications from the gateway |
| GET | `/api/payments/webhook-events/`, POST `…/{id}/retry/` | Adm, Fin | Received webhooks; re-apply a failed one |

### Dashboard, reports and audit

| Method | Path | Roles | Purpose |
|---|---|---|---|
| GET | `/api/dashboard/summary/` | All | Expected, collected, cash with agents, received at branches, deposits, settled, outstanding and discrepancies |
| GET | `/api/dashboard/trend/`, `…/lifecycle/` | All | Daily trend; how far collected money has moved towards the company account |
| GET | `/api/dashboard/branches/`, `…/agents/` | Adm, Fin, Mgr | Per-branch and per-agent breakdowns |
| GET | `/api/reports/collections.csv`, `submissions.csv`, `deposits.csv`, `discrepancies.csv` | All (deposits: Adm, Fin, Mgr) | CSV exports |
| GET | `/api/audit-logs/` | Adm, Fin, Mgr | Audit trail of every change |
| GET | `/api/health/` | Public | Health check |

Dashboard and report endpoints accept the filters `date_from`, `date_to`, `branch`, `agent` and `status`.

## Example

Sign in as an agent and record a cash repayment:

```bash
API=http://localhost:8000/api
TOKEN=$(curl -s -X POST $API/auth/login/ -H 'Content-Type: application/json' \
  -d '{"username": "agent.blr1", "password": "Demo@12345"}' | jq -r .access)

curl -s -X POST $API/collections/ \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"loan_id": 11, "amount": "2000.00", "remarks": "Part payment"}'
```

`201 Created` returns the receipt (`RCT-BLR01-…`) with the instalments it paid and the loan balance after it. Sending the same request again with the same key returns the same receipt with `200`; a new key with the same loan and amount within 10 minutes returns `409 POSSIBLE_DUPLICATE`.
