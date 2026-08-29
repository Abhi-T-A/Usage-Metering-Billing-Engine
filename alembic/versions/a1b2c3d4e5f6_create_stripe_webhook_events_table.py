"""create stripe webhook events table

Revision ID: a1b2c3d4e5f6
Revises: eefa458984e2
Create Date: 2026-08-29 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'eefa458984e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stripe_webhook_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_event_id', sa.String(length=255), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_stripe_webhook_events_stripe_event_id'),
        'stripe_webhook_events',
        ['stripe_event_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_stripe_webhook_events_stripe_event_id'),
        table_name='stripe_webhook_events',
    )
    op.drop_table('stripe_webhook_events')
