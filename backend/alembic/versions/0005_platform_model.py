"""add platform model library table

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24 01:00:00

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'platform_models',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('framework', sa.String(32), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('required_vram_gb', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source', sa.String(32), nullable=False, server_default='huggingface'),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('minio_key', sa.String(256), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_platform_models_name', 'platform_models', ['name'], unique=True)
    op.create_index('ix_platform_models_published', 'platform_models', ['is_published', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_platform_models_published', table_name='platform_models')
    op.drop_index('ix_platform_models_name', table_name='platform_models')
    op.drop_table('platform_models')
