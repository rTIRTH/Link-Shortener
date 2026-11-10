"""link on/off switch and its history

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-10 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing links stay on: the default is "true".
    op.add_column('links', sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_table('link_toggles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('link_id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['link_id'], ['links.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_link_toggles_link_id'), 'link_toggles', ['link_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_link_toggles_link_id'), table_name='link_toggles')
    op.drop_table('link_toggles')
    op.drop_column('links', 'is_active')
