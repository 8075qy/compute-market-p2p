"""add task execution slice_index for parallel dispatch

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23 15:00:00

"""
import sqlalchemy as sa

from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'task_executions',
        sa.Column('slice_index', sa.Integer(), nullable=False, server_default='0'),
    )
    op.drop_constraint('uq_task_attempt', 'task_executions', type_='unique')
    op.create_unique_constraint(
        'uq_task_attempt', 'task_executions', ['task_id', 'slice_index', 'attempt_no']
    )


def downgrade() -> None:
    op.drop_constraint('uq_task_attempt', 'task_executions', type_='unique')
    op.create_unique_constraint(
        'uq_task_attempt', 'task_executions', ['task_id', 'attempt_no']
    )
    op.drop_column('task_executions', 'slice_index')
