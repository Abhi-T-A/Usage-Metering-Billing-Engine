PROJECT
Usage Metering & Billing Engine

PROBLEM
Track SaaS usage, enforce quotas, calculate costs,
and synchronize Stripe subscriptions safely.

STACK
Python + FastAPI
PostgreSQL
SQLAlchemy
Alembic
Stripe Test Mode
Pytest
Docker

CORE ENTITIES
Tenant
Plan
Subscription
UsageEvent

USAGE TYPES
API Calls
AI Tokens

CORE APIs
GET  /health
POST /generate
GET  /usage
POST /billing/checkout
POST /webhooks/stripe

CRITICAL GUARANTEES
Idempotent metering
Quota enforcement
Integer money calculation
Verified Stripe webhooks
Webhook deduplication
Tenant isolation

NON-GOAL
Real invoicing / proration / overage billing
