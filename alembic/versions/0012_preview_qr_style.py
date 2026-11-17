"""preview page and QR code style

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-16 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing links keep redirecting straight away and keep the plain QR code.
    op.add_column('links', sa.Column('preview', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('links', sa.Column('preview_message', sa.String(length=200), nullable=True))
    op.add_column('links', sa.Column('qr_fg', sa.String(length=7), nullable=True))
    op.add_column('links', sa.Column('qr_bg', sa.String(length=7), nullable=True))
    op.add_column('links', sa.Column('qr_logo', sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    for name in ('qr_logo', 'qr_bg', 'qr_fg', 'preview_message', 'preview'):
        op.drop_column('links', name)
