"""extend notification types for realtime task/node events

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-24 10:00:00

"""
import sqlalchemy as sa

from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

NEW_VALUES = (
    'task_assigned',
    'task_started',
    'task_cancelled',
    'node_online',
    'node_offline',
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    for value in NEW_VALUES:
        op.execute(sa.text(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'"))


def downgrade() -> None:
    # PostgreSQL 不支持删除枚举值，回滚时保留既有值
    pass
