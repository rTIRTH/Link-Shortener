"""colour scheme (classic / neon) for each user

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-19 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Everybody keeps the colours they have today.
    op.add_column('users', sa.Column('color_scheme', sa.String(length=10), server_default='default', nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'color_scheme')
