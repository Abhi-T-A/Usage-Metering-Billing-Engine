from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    api_call_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    ai_token_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    price_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    tenants = relationship(
        "Tenant",
        back_populates="plan",
    )

    subscriptions = relationship(
        "Subscription",
        back_populates="plan",
    )