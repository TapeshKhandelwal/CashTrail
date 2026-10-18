# Setup

Two ways to run CashTrail locally. Configuration is described in [ENVIRONMENT.md](ENVIRONMENT.md); the demo logins are in the [README](README.md#test-credentials).

## Option A: Docker (one command)

Requires Docker with Compose v2. From the repo root:

```bash
docker compose up --build
```

This starts PostgreSQL, the API and the web app, runs the migrations and loads the demo data on first start.

| URL | What |
|---|---|
| http://localhost:3000 | Web app |
| http://localhost:8000/api/docs/ | API documentation (Swagger UI) |
| http://localhost:8000/api/health/ | Health check |

- Ports taken? `FRONTEND_PORT=3200 BACKEND_PORT=8200 DB_PORT=5433 docker compose up --build`
- Start from scratch: `docker compose down -v && docker compose up --build`
- Session cookies are `Secure` in the containers; Chrome and Firefox accept them on `http://localhost`, Safari may not.

## Option B: Manual setup

Requires Python 3.13+, Node.js 20.9+ and PostgreSQL 15+.

**1. Database.** Start only the database container (`docker compose up -d db`), or create one on a local PostgreSQL (`createdb cashtrail`) and point `DATABASE_URL` at it in step 2.

**2. Backend** on http://localhost:8000:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

**3. Frontend** on http://localhost:3000, in a second terminal:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

## Demo data

`seed_demo` loads 3 branches, 14 users, 45 customers and 55 loans, and replays a few months of collections, hand-overs, deposits and settlements through the same services the API uses. It includes every exception the system handles: cash shortage and excess, a rejected hand-over, a voided receipt, failed, short and delayed deposits, gateway mismatches and work waiting for review. Dates are relative to the day it runs.

```bash
.venv/bin/python manage.py seed_demo            # skipped if the demo data is already there
.venv/bin/python manage.py seed_demo --reset    # deletes all data and reloads it (asks first)
```

## UPI payments

UPI works out of the box with the built-in mock gateway. To use Cashfree's sandbox, set `PAYMENT_PROVIDER=cashfree` and the Cashfree test keys in `backend/.env` (see [ENVIRONMENT.md](ENVIRONMENT.md#payment-gateway-upi-optional)). In the sandbox, scanning the checkout QR opens Cashfree's payment simulator (OTP `111000`), and the test UPI IDs `testsuccess@gocash` / `testfailure@gocash` simulate a successful or failed payment.

## Tests and checks

```bash
cd backend
.venv/bin/pytest -q                        # 1,200+ tests, PostgreSQL required
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/python manage.py makemigrations --check --dry-run

cd ../frontend
npm run lint
npx next typegen && npm run typecheck
npm run build
```

GitHub Actions (`.github/workflows/ci.yml`) runs these on every push and pull request.

## Scheduled jobs

Three idempotent commands, meant for cron. The app stays correct without them; they add audit entries and tidy up UPI orders.

| Command | Schedule | Purpose |
|---|---|---|
| `manage.py flag_delayed_settlements` | Daily | Audit entry for each deposit pending past the settlement SLA |
| `manage.py sync_gateway_orders` | Every 15 min | Record UPI payments whose webhook never arrived |
| `manage.py expire_gateway_orders` | Every 15 min | Expire unpaid UPI orders after the 15-minute checkout window |
