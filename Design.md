# Usage Metering & Billing Engine

## Complete Design Document — Phase 1

> **FlyRank Backend Track Capstone**
> **Stack:** Python + FastAPI + PostgreSQL + SQLAlchemy + Alembic + Stripe Test Mode + Pytest + Docker
> **Repository:** `flyrank-capstone-metering-billing`

This design follows the capstone brief's required scope and Phase 1 deliverable: **problem, data model, API surface, layer sketch, and an explicit non-goal**. 

---

# 1. Project Overview

## 1.1 Project Name

**Usage Metering & Billing Engine**

## 1.2 Purpose

The system is a backend service for SaaS applications that answers three core questions:

1. **How much has a customer used?**
2. **How much should that usage cost?**
3. **Has the customer reached their plan limits?**

The system meters usage, enforces subscription quotas, calculates usage costs, and synchronizes subscription state with Stripe Test Mode. 

---

# 2. Problem Statement

SaaS applications commonly charge customers based on usage such as API requests or AI-token consumption.

A billing system must remain correct even when:

* clients retry requests,
* network failures cause duplicate requests,
* customers reach exactly their quota,
* Stripe sends the same webhook more than once,
* webhook signatures are invalid,
* token categories have different prices,
* money calculations require exact precision.

A mistake can result in:

* duplicate usage,
* customers receiving unauthorized access,
* incorrect billing,
* lost revenue.

The primary goal of this project is therefore:

> **Build a reliable usage metering and billing backend that maintains correct usage, quota, cost, and subscription state under retries, failures, and duplicate events.**

The capstone specifically identifies idempotent metering, quota boundaries, token pricing, and Stripe webhooks as the major correctness challenges. 

---

# 3. Goals

## 3.1 Functional Goals

The system will:

* Manage SaaS tenants.
* Assign subscription plans.
* Track API-call usage.
* Track AI-token usage.
* Enforce monthly quotas.
* Prevent duplicate usage through idempotency.
* Calculate usage costs.
* Provide monthly usage summaries.
* Create Stripe Checkout sessions.
* Process Stripe subscription webhooks.
* Verify webhook signatures.
* Prevent duplicate webhook processing.
* Synchronize tenant subscription state.

---

# 4. Core Scope

The capstone intentionally defines a small core:

```text
2 Plans
    ↓
Free
Pro

2 Usage Types
    ↓
API Calls
AI Tokens

1 Billable Endpoint
    ↓
POST /generate
```

The AI usage can be simulated; an actual AI model or API key is **not required**. 

---

# 5. Subscription Plans

## Free

```text
API calls: 1,000 / month
AI tokens: 100,000 / month
```

## Pro

The Pro plan provides higher limits.

The exact Pro pricing and limits will be defined as configuration/seed data rather than hard-coded into business logic.

The capstone explicitly defines the Free limits and describes Pro as having higher limits. 

---

# 6. Usage Types

We will support exactly two core usage types:

```text
API_CALL
AI_TOKENS
```

### API Call

One successful billable API operation records:

```text
quantity = 1
```

### AI Tokens

The dummy `/generate` endpoint can receive simulated token counts:

```json
{
  "input_tokens": 1200,
  "cached_input_tokens": 200,
  "output_tokens": 800,
  "reasoning_tokens": 100
}
```

No actual AI model invocation is required. 

---

# 7. High-Level Architecture

```text
                         ┌─────────────────┐
                         │     Client      │
                         └────────┬────────┘
                                  │
                              JWT / Request
                                  │
                                  ▼
                         ┌─────────────────┐
                         │    FastAPI      │
                         │   HTTP Layer    │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Authentication  │
                         │ & Authorization │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Service Layer  │
                         │                 │
                         │ Metering        │
                         │ Quota           │
                         │ Pricing         │
                         │ Subscription    │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Repository      │
                         │ Layer           │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │   PostgreSQL    │
                         └─────────────────┘


              ┌───────────────────────────────┐
              │       Stripe Test Mode       │
              └───────────────┬───────────────┘
                              │
                       Signed Webhook
                              │
                              ▼
                  ┌────────────────────────┐
                  │ /webhooks/stripe       │
                  │                        │
                  │ Verify signature       │
                  │ Deduplicate event      │
                  │ Update subscription    │
                  └────────────────────────┘
```

The capstone's intended architecture has a **metering path, usage read path, and payment-sync path**, with signature verification and webhook deduplication. 

---

# 8. Layered Architecture

## 8.1 API Layer

Responsible for:

* HTTP requests
* authentication
* validation
* HTTP status codes
* response serialization

It should **not contain billing business logic**.

---

## 8.2 Service Layer

Responsible for business rules:

```text
MeteringService
QuotaService
PricingService
SubscriptionService
```

Examples:

```text
MeteringService
→ record usage
→ handle idempotency

QuotaService
→ determine limits
→ check requested usage

PricingService
→ calculate cost

SubscriptionService
→ synchronize tenant plan/status
```

---

## 8.3 Repository Layer

Responsible for persistence:

```text
TenantRepository
UsageRepository
SubscriptionRepository
PlanRepository
```

The service layer should not directly contain SQL queries.

---

## 8.4 Database Layer

PostgreSQL stores:

```text
Plans
Tenants
Subscriptions
Usage Events
```

with migrations managed through Alembic.

The capstone requires real persistence with schema migrations, appropriate indexes, and tenant isolation. 

---

# 9. Data Model

## 9.1 Entity Relationship

```text
                 ┌──────────────┐
                 │    PLANS     │
                 ├──────────────┤
                 │ id PK        │
                 │ name         │
                 │ api_limit    │
                 │ token_limit  │
                 │ price_cents  │
                 └──────┬───────┘
                        │
                        │ 1:N
                        ▼
                 ┌──────────────┐
                 │   TENANTS    │
                 ├──────────────┤
                 │ id PK        │
                 │ name         │
                 │ plan_id FK   │
                 │ created_at   │
                 │ updated_at   │
                 └──────┬───────┘
                        │
              ┌─────────┴──────────┐
              │                    │
             1:N                  1:N
              │                    │
              ▼                    ▼
      ┌───────────────┐    ┌─────────────────┐
      │SUBSCRIPTIONS  │    │ USAGE_EVENTS    │
      ├───────────────┤    ├─────────────────┤
      │ id PK         │    │ id PK           │
      │ tenant_id FK  │    │ tenant_id FK    │
      │ plan_id FK    │    │ type            │
      │ stripe_cust   │    │ quantity        │
      │ stripe_sub    │    │ idempotency_key │
      │ status        │    │ created_at      │
      │ period_start  │    └─────────────────┘
      │ period_end    │
      └───────────────┘
```

---

# 10. Database Tables

## `plans`

```text
id
name
api_call_limit
ai_token_limit
price_cents
created_at
updated_at
```

Money is represented as an integer because the brief explicitly requires integer cents/micro-units rather than floating-point values. 

---

## `tenants`

```text
id
name
plan_id
created_at
updated_at
```

Every tenant has a plan.

---

## `subscriptions`

```text
id
tenant_id
plan_id
stripe_customer_id
stripe_subscription_id
status
current_period_start
current_period_end
created_at
updated_at
```

Stripe is the payment source of truth; our database mirrors its state through verified events. 

---

## `usage_events`

```text
id
tenant_id
type
quantity
idempotency_key
created_at
```

A usage event records:

* tenant
* usage type
* quantity
* timestamp
* idempotency key

as specified in the capstone glossary. 

---

# 11. Critical Database Constraint

The most important constraint is:

```sql
UNIQUE (tenant_id, idempotency_key)
```

This guarantees that:

```text
Tenant A + key ABC
```

can exist once, while:

```text
Tenant B + key ABC
```

is allowed.

This is necessary because the same request may be retried, and the capstone requires exactly one usage event for the same tenant and idempotency key. 

---

# 12. Idempotency Strategy

The metering flow:

```text
POST /generate
       │
       ▼
Read Idempotency-Key
       │
       ▼
Check existing event
       │
    ┌──┴──┐
    │     │
 Exists  New
    │     │
    ▼     ▼
Return  Quota Check
original    │
result      ▼
         Record usage
             │
             ▼
          Commit
```

However, the database constraint is the final safety mechanism.

We will use:

```text
Application check
       +
Database UNIQUE constraint
       +
Database transaction
```

This protects against concurrent requests that arrive at the same time.

---

# 13. Quota Enforcement

Before a billable action is allowed:

```text
Current Usage
      +
Requested Usage
      │
      ▼
Plan Limit
      │
      ▼
Within limit?
   /       \
 YES       NO
  │         │
  ▼         ▼
Allow     Reject
```

The capstone explicitly requires quota enforcement **before** the billable action. 

---

# 14. Quota Boundary Rules

We will test:

```text
999 / 1000 + 1
```

→ allowed.

```text
1000 / 1000 + 1
```

→ rejected.

The evaluator specifically tests:

* just below quota
* exact quota boundary
* request after quota

and expects the documented `429 / 402` behavior. 

---

# 15. HTTP Status Strategy

| Situation                             | Status |
| ------------------------------------- | -----: |
| Successful request                    |  `200` |
| Successful resource/session creation  |  `201` |
| Invalid request                       |  `400` |
| Missing/invalid authentication        |  `401` |
| Plan/payment restriction              |  `402` |
| Resource not found                    |  `404` |
| Idempotency conflict where applicable |  `409` |
| Usage quota exceeded                  |  `429` |
| Unexpected server failure             |  `500` |

The important requirement is that bad input produces a clean `4xx` response rather than an accidental `500`, and quota errors are clearly communicated.  

---

# 16. API Surface

## `GET /health`

Purpose:

```text
Service health check
```

Response:

```json
{
  "status": "ok"
}
```

---

## `POST /generate`

### Purpose

Dummy billable operation.

### Headers

```text
Authorization: Bearer <JWT>
Idempotency-Key: <unique-key>
```

### Request

```json
{
  "input_tokens": 1200,
  "cached_input_tokens": 200,
  "output_tokens": 800,
  "reasoning_tokens": 100
}
```

### Success

```json
{
  "request_id": "req_abc123",
  "usage": {
    "api_calls": {
      "used": 426,
      "limit": 1000
    },
    "ai_tokens": {
      "used": 42300,
      "limit": 100000
    }
  },
  "cost_cents": 15
}
```

---

# 17. `GET /usage`

Returns current monthly usage:

```json
{
  "tenant_id": "tenant_123",
  "period": "2026-08",
  "api_calls": {
    "used": 426,
    "limit": 1000
  },
  "ai_tokens": {
    "used": 42300,
    "limit": 100000
  },
  "cost_cents": 125
}
```

The brief's architecture specifically describes `/usage` as a rollup of usage events returning **used, limit, and cost**. 

---

# 18. `POST /billing/checkout`

Creates a Stripe Test Mode Checkout session.

### Request

```json
{
  "plan": "pro"
}
```

### Response

```json
{
  "checkout_url": "https://checkout.stripe.com/..."
}
```

No real money is involved. Stripe Test Mode and the Stripe CLI are explicitly required for this capstone's payment integration. 

---

# 19. `POST /webhooks/stripe`

Stripe sends:

```text
checkout.session.completed
customer.subscription.updated
customer.subscription.deleted
```

The handler:

```text
Receive request
      │
      ▼
Verify Stripe signature
      │
   ┌──┴──┐
 Invalid Valid
   │       │
   ▼       ▼
  400   Check event ID
             │
          ┌──┴──┐
       Duplicate New
          │       │
          ▼       ▼
        Ignore  Process
                    │
                    ▼
              Update tenant
```

The required webhook events and verification/deduplication behavior are specified in the brief. 

---

# 20. Authentication & Authorization

**Implementation decision:** JWT-based authentication.

This is our chosen implementation; the capstone only requires real authorization and does not prescribe JWT specifically.

JWT payload:

```json
{
  "sub": "user_123",
  "tenant_id": "tenant_001",
  "role": "OWNER"
}
```

For protected endpoints, the tenant comes from the authenticated identity.

We will **not trust a client-provided `tenant_id`** for authorization.

---

# 21. Tenant Isolation

Every tenant-scoped query must include the authenticated tenant:

```sql
WHERE tenant_id = :authenticated_tenant_id
```

Example:

```text
Tenant A
   ↓
JWT
   ↓
tenant_id = A
   ↓
GET /usage
   ↓
only A's events
```

Tenant A must never be able to access Tenant B's usage.

Tenant isolation is explicitly part of the required database design. 

---

# 22. Cost Calculation

The pricing service will handle:

```text
API calls
+
Input tokens
+
Cached input tokens
+
Output tokens
+
Reasoning tokens
```

The pricing rules are:

* cached input tokens are cheaper,
* reasoning tokens count as output,
* token categories must not simply be added together incorrectly.

Pricing constants will be pinned in configuration and covered by deterministic tests. 

---

# 23. Money Representation

We will never use:

```python
float
```

for money.

Instead:

```text
price_cents: int
cost_cents: int
```

Example:

```text
$0.02
```

is represented as:

```text
2 cents
```

This prevents floating-point precision problems and follows the explicit capstone rule. 

---

# 24. Monthly Usage Rollup

We don't need a separate monthly usage table in the core system.

Instead:

```text
usage_events
      │
      ▼
Filter current month
      │
      ▼
GROUP BY usage type
      │
      ▼
SUM(quantity)
      │
      ▼
used / limit / cost
```

This follows the intended architecture of rolling up `usage_events` for `/usage`. 

---

# 25. Stripe Synchronization

The database does not independently decide that a payment succeeded.

Instead:

```text
Stripe
   │
   │ verified webhook
   ▼
Our backend
   │
   ▼
Subscription state
   │
   ▼
Tenant plan
```

This keeps payment truth in Stripe and our database as the synchronized application state.

---

# 26. Security Design

The system will implement:

### Authentication

JWT for protected APIs.

### Authorization

Tenant-scoped access.

### Input validation

Pydantic request validation.

### Stripe security

Signature verification.

### Secret management

Environment variables only:

```text
DATABASE_URL
JWT_SECRET
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
```

No secrets committed to Git.

The capstone explicitly states Stripe secrets belong in `.env`, which must be git-ignored. 

---

# 27. Error Handling

Standard error format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation"
  }
}
```

Example:

```json
{
  "error": {
    "code": "API_QUOTA_EXCEEDED",
    "message": "Monthly API call quota exceeded",
    "used": 1000,
    "limit": 1000
  }
}
```

This ensures API failures are both **machine-readable and understandable**.

---

# 28. Testing Strategy

Testing is a major part of this capstone.

The brief explicitly says tests must cover:

* duplicate usage prevention,
* quota boundary cases,
* cost calculations,
* invalid webhook rejection,
* duplicate webhook handling. 

Our tests will be organized as:

```text
tests/
├── test_health.py
├── test_metering.py
├── test_quota.py
├── test_pricing.py
└── test_stripe_webhook.py
```

---

# 29. Critical Test Cases

## Idempotency

```text
Same tenant
Same idempotency key
Same request

Expected:
1 usage event
```

## Quota

```text
999 + 1 → allowed
1000 + 1 → rejected
```

## Pricing

```text
Normal input
Cached input
Output
Reasoning
```

## Stripe

```text
Invalid signature → 400
Valid event → processed
Same event twice → processed once
```

These correspond directly to the capstone's acceptance probes. 

---

# 30. Background Job

The shared capstone requirements require **at least one background job** for slow/bulk work, with retries and failure handling. 

For the core implementation, we'll keep the synchronous billing path small and introduce a background reconciliation/maintenance job if needed.

A sensible implementation is:

```text
Scheduler
    │
    ▼
Reconciliation Job
    │
    ├── Compare local subscription state
    │
    └── Detect stale/missed synchronization
```

This will be implemented **after the core billing flow works**, so it doesn't unnecessarily complicate the critical path.

---

# 31. Repository Structure

```text
flyrank-capstone-metering-billing/
│
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── generate.py
│   │   │   ├── usage.py
│   │   │   └── billing.py
│   │   │
│   │   └── webhooks/
│   │       └── stripe.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   │
│   ├── models/
│   │   ├── plan.py
│   │   ├── tenant.py
│   │   ├── subscription.py
│   │   └── usage_event.py
│   │
│   ├── schemas/
│   │   ├── generate.py
│   │   ├── usage.py
│   │   └── billing.py
│   │
│   ├── services/
│   │   ├── metering_service.py
│   │   ├── quota_service.py
│   │   ├── pricing_service.py
│   │   └── subscription_service.py
│   │
│   ├── repositories/
│   │   ├── plan_repository.py
│   │   ├── tenant_repository.py
│   │   ├── usage_repository.py
│   │   └── subscription_repository.py
│   │
│   └── main.py
│
├── tests/
│   ├── test_health.py
│   ├── test_metering.py
│   ├── test_quota.py
│   ├── test_pricing.py
│   └── test_stripe_webhook.py
│
├── alembic/
│   └── versions/
│
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
├── README.md
├── capstone.yaml
├── EVIDENCE.md
├── BUILDLOG.md
└── LICENSE
```

---

# 32. Non-Goals

The following are explicitly outside the core scope:

```text
❌ Real payment processing
❌ Production Stripe mode
❌ Real AI model calls
❌ Full invoicing
❌ Proration
❌ Overage billing
```

The brief explicitly excludes invoicing, proration, and overage billing from the core and lists them as stretch goals. 

---

# 33. Possible Stretch Goals

Only after the core passes all acceptance probes:

### 1. Usage Alerts

```text
80% quota → notification
100% quota → notification
```

### 2. Overage Billing

Allow usage beyond quota and calculate additional charges.

### 3. Invoices

Generate monthly statements with usage line items.

### 4. Proration

Handle mid-cycle plan upgrades.

### 5. Reconciliation

Compare local subscription state against Stripe periodically.

These are explicitly suggested by the capstone. 

---

# 34. Definition of Done

Our project is **not considered complete** just because the endpoints work.

The final system must demonstrate:

```text
✅ Idempotent metering
✅ No duplicate usage
✅ Correct quota enforcement
✅ Correct 429 / 402 behavior
✅ Monthly usage rollup
✅ Correct cost calculation
✅ Integer money representation
✅ Stripe Checkout
✅ Verified webhooks
✅ Duplicate webhook protection
✅ Tenant isolation
✅ Authentication / authorization
✅ Database migrations
✅ Tests
✅ Docker setup
✅ README
✅ Architecture diagram
✅ EVIDENCE.md
✅ BUILDLOG.md
✅ capstone.yaml
```

These map directly to the capstone's Definition of Done and acceptance requirements. 

---

# 35. Acceptance Test Plan

The evaluator has five important behavioral probes:

### Probe 1 — Idempotency

```text
Same billable request
+
Same idempotency key
× 2
```

Expected:

```text
Exactly 1 usage event
Second response mirrors first
```

### Probe 2 — Quota

```text
Drive tenant to quota
→ boundary behavior

Next request
→ 429 / 402
```

### Probe 3 — Stripe Upgrade

```text
Free
 ↓
Stripe Test Checkout
 ↓
Webhook
 ↓
Pro
 ↓
GET /usage
 ↓
New limits
```

### Probe 4 — Webhook Security

```text
Forged webhook
→ 400
→ no state change

Real webhook × 2
→ processed once
```

### Probe 5 — Pricing

```text
Pinned pricing tests
       ↓
cached-input rules
reasoning-token rules
       ↓
exact expected totals
       ↓
GET /usage matches
```

These are the published acceptance probes in the capstone brief. 

---

# 36. Success Criteria

We are aiming for more than merely **"Ships."**

The rubric prioritizes:

| Dimension           | Weight |
| ------------------- | -----: |
| Architecture        |     ×3 |
| Correctness         |     ×3 |
| Resilience          |     ×3 |
| Security            |     ×2 |
| AI cost & grounding |     ×2 |
| Testing             |     ×2 |
| Communication       |     ×2 |

The brief explicitly says a small system that is **correct, resilient, and well-tested** is better than a larger system that fails. 

---

# 37. Development Plan

We'll implement in this order:

```text
PHASE 1 — DESIGN
────────────────────────────
✓ Problem
✓ Requirements
✓ Architecture
✓ Database
✓ API contract
✓ Authentication strategy
✓ Non-goals


PHASE 2 — CORE BILLING
────────────────────────────
1. Project setup
2. PostgreSQL
3. SQLAlchemy
4. Alembic
5. Database models
6. Seed plans + tenant
7. Authentication
8. Metering
9. Idempotency
10. Quota enforcement


PHASE 3 — STRIPE
────────────────────────────
11. Stripe configuration
12. Checkout
13. Webhook verification
14. Webhook deduplication
15. Subscription synchronization


PHASE 4 — COST + HARDENING
────────────────────────────
16. Pricing engine
17. Usage rollups
18. Error handling
19. Background job
20. Test suite
21. Security review


PHASE 5 — SUBMISSION
────────────────────────────
22. EVIDENCE.md
23. BUILDLOG.md
24. capstone.yaml
25. README
26. Architecture diagram
27. Demo rehearsal
```

---

# ✅ Phase 1 — COMPLETE

We now have a complete design covering:

**Problem → Requirements → Architecture → Data Model → Database Constraints → API Contract → Authentication → Tenant Isolation → Metering → Quotas → Pricing → Stripe → Testing → Security → Non-goals → Acceptance Criteria → Development Plan.**

The next step is **not more design**.

## 🔥 Phase 2.1 — Create the actual project

We'll now build:

```text
FastAPI
   ↓
Docker Compose
   ↓
PostgreSQL
   ↓
SQLAlchemy
   ↓
Alembic
   ↓
GET /health
```

and establish the first Git commit with the required repository hygiene. The capstone specifically asks for the public repository to exist from day one, with a README skeleton and `.gitignore` in the first commit.
