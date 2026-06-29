# Zenith — Backend

A Flask JSON API for the Zenith fintech dashboard. SQLAlchemy + SQLite, bcrypt password hashing, JWT auth, atomic transfers, money stored as integer minor units (kobo) to avoid float rounding.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then fill in real random secrets — see below
python run.py
```

Runs on **http://127.0.0.1:5050** by default. On first run, it seeds two demo users:

| Email | Password | Starting balance |
|---|---|---|
| daniel@example.com | Prayer123 | ₦1,000.00 |
| sharon@example.com | Sunrise123 | ₦500.00 |

Generate real secrets for `.env` rather than using placeholders:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## API

All endpoints are under `/api`. JSON in, JSON out.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | — | Create account, returns tokens |
| POST | `/auth/login` | — | Returns tokens |
| POST | `/auth/refresh` | refresh token | New access token |
| GET | `/auth/me` | access token | Current user + account |
| GET | `/accounts/me` | access token | Current balance |
| POST | `/accounts/change-password` | access token | Change password |
| GET | `/transactions/history` | access token | Paginated, `?page=&perPage=` |
| POST | `/transactions/deposit` | access token | `{amount}` |
| POST | `/transactions/withdraw` | access token | `{amount}` |
| POST | `/transactions/transfer` | access token | `{receiverAccountNumber, amount, description?}` |
| POST | `/transactions/airtime` | access token | `{amount, phone}` |

Errors come back as `{"error": "message", "field": "amount"}` with a 400/401/404/500 status.

## What changed from the original prototype

The original version (a single `app.py`) stored users and balances in plain Python dicts — passwords in plaintext, balances reset on every restart, no transaction record, no validation on amounts, and no protection against two requests racing on the same balance. This version instead has:

- **Persistence**: SQLAlchemy models (`User`, `Account`, `Transaction`) backed by SQLite (swap `DATABASE_URL` for Postgres in production).
- **Password hashing**: bcrypt, 12 rounds.
- **JWT auth** instead of server-side sessions, since the frontend is a separate SPA.
- **Validation** (`app/validation.py`): every amount, email, password, and phone number is checked server-side before touching the database.
- **Atomic, locked transfers**: `transfer` locks both the sender's and receiver's account rows (in a fixed order, to avoid deadlocks) before mutating either balance, and writes both legs of the transfer in one commit.
- **Integer money**: balances are stored as `balance_minor` (kobo), not floats, so nothing gets silently rounded.
- **A real transaction ledger**: every deposit, withdrawal, transfer, and airtime purchase is recorded with a running `balance_after`, instead of mutating a balance with no history.

## Known limitations — read before using this for anything real

- **SQLite locking is not real row-level locking.** `with_for_update()` is a no-op on SQLite; it falls back to SQLite's own file-level locking, which is fine for a single local dev instance but won't give you correct concurrent-transfer semantics under load. On Postgres, the same code gives you a genuine row lock — switch `DATABASE_URL` before this goes anywhere near concurrent traffic.
- **No rate limiting, audit logging, or idempotency keys.** A retried request to `/transfer` will execute twice. Real payment systems use idempotency keys to prevent this.
- **No KYC, fraud checks, or regulatory compliance** of any kind — this is a learning/demo skeleton, not a path to a licensed money-transmission product.
- **CORS is wide open to one origin** (`FRONTEND_ORIGIN` in `.env`) — fine for local dev, but revisit before any public deployment.
- **The Flask dev server** (`app.run()`) is not production-grade — use gunicorn/uwsgi behind a real web server before deploying anywhere.
