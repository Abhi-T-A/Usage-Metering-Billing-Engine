# Usage Metering & Billing Engine — Phase 1 Design Document

> **FlyRank Backend Track Capstone Project**  
> **Repository:** `flyrank-capstone-metering-billing` / `Usage-Metering-Billing-Engine`  
> **Stack:** Python 3.12, FastAPI, PostgreSQL, SQLAlchemy 2.0, Alembic, Stripe Test Mode, Pytest

---

## 1. Problem Statement
Modern SaaS applications bill customers based on consumption (API calls and AI token usage). The billing backend must maintain strict correctness under real-world conditions:
- Network retries and duplicate requests must never double-count usage or overcharge customers.
- Plan quota boundaries must be enforced before billable execution.
- Money calculations require exact precision without floating-point inaccuracies.
- Stripe subscriptions must be securely synchronized via signature-verified, deduplicated webhooks.

---

## 2. Data Model & Entity Relationships

```text
       ┌──────────────┐
       │    PLANS     │
       ├──────────────┤
       │ id (PK)      │
       │ name (UQ)    │
       │ api_call_lim │
       │ ai_token_lim │
       │ price_cents  │
       └──────┬───────┘
              │ 1:N
              ▼
       ┌──────────────┐
       │   TENANTS    │
       ├──────────────┤
       │ id (PK)      │
       │ name         │
       │ plan_id (FK) │
       │ api_key_hash │
       └──────┬───────┘
              │
       ┌──────┴───────────────┐
       │ 1:N                  │ 1:N
       ▼                      ▼
┌───────────────┐      ┌───────────────────────────────┐
│ SUBSCRIPTIONS │      │         USAGE_EVENTS          │
├───────────────┤      ├───────────────────────────────┤
│ id (PK)       │      │ id (PK)                       │
│ tenant_id(FK) │      │ tenant_id (FK)                │
│ plan_id (FK)  │      │ type (VARCHAR)                │
│ stripe_cust_id│      │ quantity (INT)                │
│ stripe_sub_id │      │ idempotency_key (VARCHAR)     │
│ status        │      │ created_at (TIMESTAMP)        │
│ period_start  │      ├───────────────────────────────┤
│ period_end    │      │ UNIQUE(tenant_id, idemp_key)  │
└───────────────┘      └───────────────────────────────┘
```

---

## 3. Layer Sketch

```text
HTTP Layer (FastAPI Routes)
  │  - Parses HTTP requests & extracts Headers (X-API-Key, Idempotency-Key, Stripe-Signature)
  │  - Enforces boundary validation (Pydantic v2)
  │  - Maps domain exceptions to HTTP status codes (201, 200, 400, 401, 402, 429)
  ▼
Service Layer (Business Logic)
  │  - MeteringService: Idempotency check -> Quota check -> Transactional persistence
  │  - QuotaService: Calculates month-to-date usage vs plan limits
  │  - PricingService: Exact integer micro-cent arithmetic for token categories
  │  - WebhookService: Signature verification, replay deduplication, atomic plan update
  ▼
Repository Layer (Data Access)
  │  - PlanRepository, TenantRepository, SubscriptionRepository, UsageRepository, WebhookEventRepository
  │  - Strictly isolates queries by tenant_id
  ▼
Database Layer (PostgreSQL)
  │  - Schema versioned via Alembic migrations
  │  - UNIQUE(tenant_id, idempotency_key) guarantees database-level integrity
```

---

## 4. API Surface

| Method | Endpoint | Auth | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | None | Service liveness probe |
| `POST` | `/generate` | `X-API-Key`, `Idempotency-Key` | Idempotent billable operation with quota enforcement |
| `GET` | `/usage` | `X-API-Key` | Current monthly usage rollup, remaining quotas & costs |
| `POST` | `/billing/checkout` | `X-API-Key` | Creates Stripe subscription checkout session |
| `POST` | `/webhooks/stripe` | `Stripe-Signature` | Processes verified Stripe events (`checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`) |

---

## 5. Explicit Non-Goals
1. **No Real Payment Processing:** Operates exclusively in Stripe Test Mode using mock payment cards (`4242...`).
2. **No Real AI Model Invocations:** Simulates token counts to focus strictly on metering and billing correctness without external LLM provider dependencies.
3. **No Mid-Cycle Proration in Core:** Plan upgrades take effect immediately upon webhook confirmation; complex proration credits are deferred as stretch goals.
4. **No Direct Tenant ID Trust:** `tenant_id` is never accepted from client payload bodies or query parameters.
