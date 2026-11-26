"""email alerts for links (click limit reached, N clicks, about to end)

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-25 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None

SENT = ('alert_limit_sent_at', 'alert_expiry_sent_at', 'alert_clicks_sent_at')


def upgrade() -> None:
    # Every existing link has alerts off, so nothing changes until the owner turns them on.
    op.add_column('links', sa.Column('alert_limit', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('links', sa.Column('alert_expiry', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('links', sa.Column('alert_clicks', sa.Integer(), nullable=True))
    for name in SENT:
        op.add_column('links', sa.Column(name, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for name in (*reversed(SENT), 'alert_clicks', 'alert_expiry', 'alert_limit'):
        op.drop_column('links', name)
