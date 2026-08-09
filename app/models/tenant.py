from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id"),
        nullable=False,
    )
    api_key_hash: Mapped[str] = mapped_column(
    String(255),
    unique=True,
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

    plan = relationship(
        "Plan",
        back_populates="tenants",
    )

    subscriptions = relationship(
        "Subscription",
        back_populates="tenant",
    )

    usage_events = relationship(
        "UsageEvent",
        back_populates="tenant",
    )