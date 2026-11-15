"""click limit, archive, and tags

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-15 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both nullable: existing links have no limit and are not archived.
    op.add_column('links', sa.Column('click_limit', sa.Integer(), nullable=True))
    op.add_column('links', sa.Column('limit_reached_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('links', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('tags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=24), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'name', name='uq_tags_user_name')
    )
    op.create_index(op.f('ix_tags_user_id'), 'tags', ['user_id'], unique=False)
    op.create_table('link_tags',
    sa.Column('link_id', sa.Integer(), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['link_id'], ['links.id'], ),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ),
    sa.PrimaryKeyConstraint('link_id', 'tag_id')
    )


def downgrade() -> None:
    op.drop_table('link_tags')
    op.drop_index(op.f('ix_tags_user_id'), table_name='tags')
    op.drop_table('tags')
    op.drop_column('links', 'archived_at')
    op.drop_column('links', 'limit_reached_at')
    op.drop_column('links', 'click_limit')
