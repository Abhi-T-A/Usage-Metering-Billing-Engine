# Usage Metering & Billing Engine

> **FlyRank Backend Track Capstone Project**  
> **Stack:** Python + FastAPI + PostgreSQL + SQLAlchemy + Alembic + Stripe Test Mode + Pytest + Docker

A reliable backend service for SaaS applications to meter usage (API calls & AI tokens), enforce subscription quotas, calculate usage costs, and synchronize subscription state with Stripe Test Mode.

---

## 📖 Architecture & Design

See full Phase 1 Design Document in [Docs/DESIGN.md](file:///d:/Usage-Metering-Billing-Engine/Docs/DESIGN.md) or [Design.md](file:///d:/Usage-Metering-Billing-Engine/Design.md).

---

## 🛠 Features Scope

- **SaaS Tenant Isolation**: Dynamic tenant resolution via JWT.
- **Idempotent Usage Metering**: Safe usage recording under network retries via `UNIQUE(tenant_id, idempotency_key)`.
- **Quota Enforcement**: Hard boundary checking (`429` / `402`) prior to billable execution.
- **AI Token Pricing Engine**: Differentiated rates for input, cached-input, output, and reasoning tokens using exact integer money calculations (`cents`).
- **Stripe Synchronization**: Verified webhook ingestion and deduplication.

---

## 🚀 Getting Started

*(Development setup instructions will be updated in Phase 2)*

```bash
# Clone the repository
git clone https://github.com/Abhi-T-A/Usage-Metering-Billing-Engine.git
```

---

## 📄 License

MIT
