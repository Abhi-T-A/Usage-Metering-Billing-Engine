# AI Build & Engineering Log (BUILDLOG.md)

> **Repository:** `flyrank-capstone-metering-billing` / `Usage-Metering-Billing-Engine`  
> **Stack:** Python 3.12, FastAPI, PostgreSQL, SQLAlchemy 2.0, Alembic, Stripe Test Mode, Pytest

---

## 🧭 Overview & Approach
This capstone was built through an incremental, test-driven approach across 5 structured phases. AI was leveraged for code structuring, boilerplate scaffolding, and test generation, while core correctness decisions (exact integer arithmetic, transaction boundaries, idempotent deduplication, and boundary condition guarantees) were strictly governed.

---

## 🛠️ Chronological Phase-by-Phase Build Log

### Phase 1: Architectural Design & Domain Modelling
- **Objective:** Establish data models, schema relationships, and API contracts.
- **AI Contributions:** Generated the comprehensive initial design document in `DESIGN.md` defining models for `Plan`, `Tenant`, `Subscription`, and `UsageEvent`.
- **Human Decision:** Enforced the critical database-level constraint `UNIQUE(tenant_id, idempotency_key)` on `usage_events` rather than relying solely on in-memory application checks.

---

### Phase 2: Core Metering, Quota Enforcement & Probes 1 & 2
- **Objective:** Build repository layer, `QuotaService`, `MeteringService`, and `POST /generate`.
- **AI Error & Correction:**
  - *Error:* Global vs Virtual Environment mismatch occurred when PowerShell launched `uvicorn` outside the `.venv` context where `pwdlib[argon2]` was initially installed.
  - *Resolution:* Synchronized environment dependencies across global and `.venv` environments, verifying exact package bindings.
- **Key Architectural Choices:**
  - `Idempotency-Key` was placed as an HTTP Header (RFC standard) rather than in the JSON body.
  - Idempotency checks precede quota checking: a retry of a successful call when the tenant is later at 100% quota will return the original record (`200 OK`) rather than incorrectly returning `429`.
  - Quota boundaries enforced: $999 + 1 = 1000 \le 1000$ (Allowed, `201`), $1000 + 1 = 1001 > 1000$ (Rejected, `429`).

---

### Phase 3: Stripe Integration & Probes 3 & 4
- **Objective:** Implement Stripe Checkout Sessions and signed webhook processing.
- **AI Contributions:** Scaffolded `StripeService` for session creation in `mode="subscription"` and `WebhookService` for cryptographic signature verification.
- **Correctness Rules:**
  - Verified that calling `POST /billing/checkout` **does not** prematurely upgrade the tenant's plan.
  - Created persistent table `stripe_webhook_events` with unique index on `stripe_event_id` to guarantee replay attack and duplicate webhook protection across server restarts.
  - Configured raw byte reading (`await request.body()`) before JSON parsing to prevent signature mismatch failures.
  - Added handlers for `checkout.session.completed`, `customer.subscription.updated`, and `customer.subscription.deleted`.

---

### Phase 4: Pricing Engine & Monthly Usage Rollup
- **Objective:** Implement `PricingService` (integer cents / micro-cents) and `GET /usage`.
- **AI Contributions:** Generated pure domain models for `TokenUsageBreakdown` and `PricingResult`.
- **Correctness Rules:**
  - Banned IEEE 754 `float` types from all money calculations.
  - Computed values in **micro-cents** ($1\text{ Cent} = 10,000\text{ micro-cents}$) with integer ceiling conversion `(total + 9999) // 10000`.
  - Pinned pricing categories: reasoning tokens strictly billed at output rate; cached input tokens receive a discounted rate.

---

### Phase 5: Background Reconciliation Job & Submission Pack
- **Objective:** Background cron/job comparing local DB against Stripe API with failure isolation.
- **AI Contributions:** Implemented `SubscriptionReconciler` in `app/scripts/reconciliation_job.py` with exponential backoff retries and critical alert hooks.
- **Resilience Design:** Each subscription is checked in its own try/except block with retry loops so that an API failure for one tenant never crashes the batch job.

---

## 📈 Test Suite Milestones

| Phase | Added Test Modules | Total Passing Tests |
| :--- | :--- | :---: |
| **Phase 2** | `test_auth.py`, `test_metering.py`, `test_quota.py` | 13 |
| **Phase 3** | `test_billing_checkout.py`, `test_stripe_webhook.py` | 23 |
| **Phase 4** | `test_pricing.py`, `test_usage_rollup.py` | 35 |
| **Phase 5** | `test_reconciliation.py` | **39** |

---

## 🛡️ Production Hygiene & Safety
1. **Secrets:** All secrets (`DATABASE_URL`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`) stay in `.env` (git-ignored) with safe placeholders in `.env.example`.
2. **Deterministic Tests:** In-memory SQLite with `StaticPool` runs all 39 tests in under 3.5 seconds with zero external network dependencies.
