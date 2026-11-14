"""click details: source, browser, os, country, city, visitor

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All nullable: clicks recorded before this change simply have no details.
    op.add_column('clicks', sa.Column('source', sa.String(length=24), nullable=True))
    op.add_column('clicks', sa.Column('browser', sa.String(length=16), nullable=True))
    op.add_column('clicks', sa.Column('os', sa.String(length=16), nullable=True))
    op.add_column('clicks', sa.Column('country', sa.String(length=2), nullable=True))
    op.add_column('clicks', sa.Column('city', sa.String(length=80), nullable=True))
    op.add_column('clicks', sa.Column('visitor', sa.String(length=16), nullable=True))


def downgrade() -> None:
    for name in ('visitor', 'city', 'country', 'os', 'browser', 'source'):
        op.drop_column('clicks', name)
