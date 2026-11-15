"""history of destination changes

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-15 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('link_edits',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('link_id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('old_url', sa.Text(), nullable=False),
    sa.Column('new_url', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['link_id'], ['links.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_link_edits_link_id'), 'link_edits', ['link_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_link_edits_link_id'), table_name='link_edits')
    op.drop_table('link_edits')
