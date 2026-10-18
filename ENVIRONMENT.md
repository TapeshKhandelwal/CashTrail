# Environment variables

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to `frontend/.env.local`; both files list every variable with development values. "Default" below is the value used when a variable is not set.

## Backend (`backend/.env`)

### Core

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | required | Signing key for JWTs and sessions |
| `DATABASE_URL` | required | PostgreSQL connection string (add `?sslmode=require` for hosted databases) |
| `DEBUG` | `False` | Debug mode; also turns off the HTTPS settings below |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hostnames the API may be served from |
| `LOG_LEVEL` | `INFO` | Minimum log level |
| `DB_CONN_MAX_AGE` | `60` | Seconds to keep database connections open |

### Security

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Browser origins allowed to call the API directly |
| `CSRF_TRUSTED_ORIGINS` | empty | Origins trusted for the Django admin |
| `SECURE_SSL_REDIRECT` | `True` | Redirect HTTP to HTTPS when `DEBUG=False` |
| `SECURE_HSTS_SECONDS` | `2592000` | HSTS max-age when `DEBUG=False`; `0` disables it |
| `TRUST_X_FORWARDED_FOR` | `False` | Trust one proxy's `X-Forwarded-For` for throttling and the audit trail |
| `BFF_SHARED_SECRET` | empty | Shared with the frontend server so Django can trust the browser IP it forwards. Set the same value on both |
| `JWT_ACCESS_MINUTES` | `30` | Access token lifetime |
| `JWT_REFRESH_DAYS` | `1` | Refresh token lifetime (rotated on use, revoked on logout) |
| `LOGIN_THROTTLE_RATE` | `10/min` | Login attempts per client IP |
| `LOGIN_USERNAME_THROTTLE_RATE` | `5/min` | Failed login attempts per username |
| `USER_THROTTLE_RATE` | `600/min` | Requests per signed-in user |
| `CACHE_URL` | file cache | Cache for throttle counters |
| `ADMIN_ENABLED` | value of `DEBUG` | Serve the read-only Django admin |
| `ADMIN_URL` | `admin/` | Path of the Django admin |

### Business rules

| Variable | Default | Purpose |
|---|---|---|
| `SETTLEMENT_SLA_DAYS` | `2` | Days a bank deposit may stay unsettled before it is flagged as delayed |
| `DUPLICATE_WINDOW_MINUTES` | `10` | Window in which the same loan, amount and agent is treated as a possible duplicate receipt |

### Payment gateway (UPI, optional)

| Variable | Default | Purpose |
|---|---|---|
| `PAYMENT_PROVIDER` | `mock` | `mock` (built-in, no keys needed), `cashfree` or `razorpay` |
| `CASHFREE_APP_ID` | empty | Cashfree App ID (required for `cashfree`) |
| `CASHFREE_SECRET_KEY` | empty | Cashfree secret key: API calls and webhook signatures (required for `cashfree`) |
| `CASHFREE_ENVIRONMENT` | `sandbox` | `sandbox` (test, no real money) or `production` |
| `CASHFREE_NOTIFY_URL` | empty | Public URL of `/api/payments/webhooks/cashfree/` for payment webhooks |
| `CASHFREE_RETURN_URL` | empty | Page the customer returns to when the checkout cannot open as a pop-up; `{order_id}` is filled in |
| `RAZORPAY_KEY_ID` | empty | Razorpay key id (required for `razorpay`) |
| `RAZORPAY_KEY_SECRET` | empty | Razorpay key secret (required for `razorpay`) |
| `RAZORPAY_WEBHOOK_SECRET` | empty | Razorpay webhook secret (required for `razorpay`) |

### Tests

| Variable | Default | Purpose |
|---|---|---|
| `TEST_DB_NAME` | unset | Name of the database pytest creates; use a different one for parallel runs |

## Frontend (`frontend/.env.local`)

`NEXT_PUBLIC_*` values are built into the bundle, so change them before `npm run build`.

| Variable | Default | Purpose |
|---|---|---|
| `API_URL` | `http://localhost:8000/api` | Django API base, used only by the Next.js server |
| `BFF_SHARED_SECRET` | empty | Same value as the backend's |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | API origin, so the service worker never caches API responses |
| `NEXT_PUBLIC_APP_URL` | `http://localhost:3000` | Public URL of the web app |
| `NEXT_PUBLIC_APP_VERSION` | `dev` | Service worker cache version; change it on every deploy |
| `NEXT_PUBLIC_DEMO_MODE` | off | `true` shows one-click demo sign-in on the login page |

## Docker Compose

`docker-compose.yml` sets working values for every service, so `docker compose up --build` needs no configuration. These can be overridden from the shell or a root `.env` file:

| Variable | Default | Purpose |
|---|---|---|
| `FRONTEND_PORT`, `BACKEND_PORT`, `DB_PORT` | `3000`, `8000`, `5432` | Host ports |
| `SEED_DEMO` | `true` | Load the demo data on first start |
| `SECRET_KEY`, `BFF_SHARED_SECRET` | demo values | Replace for anything other than local use |
| `PAYMENT_PROVIDER`, `CASHFREE_*`, `RAZORPAY_*` | mock gateway | Gateway settings, as above |
