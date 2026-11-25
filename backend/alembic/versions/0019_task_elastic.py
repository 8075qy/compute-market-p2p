"""add elastic scaling columns for dynamic concurrency

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-24 23:59:00

任务弹性伸缩（阶段 1 数据层）：
- Task.min_concurrency：并发下限
- Task.max_concurrency：并发上限（NULL 时回退 concurrency）
- Task.total_work_units：总工作单元（NULL = 分片数即总量模型）
- Task.completed_work_units：累计完成工作单元
- TaskExecution.completed_work_units：分片已完成工作单元
"""

import sqlalchemy as sa

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("min_concurrency", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "tasks",
        sa.Column("max_concurrency", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("total_work_units", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "completed_work_units", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "task_executions",
        sa.Column(
            "completed_work_units", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("task_executions", "completed_work_units")
    op.drop_column("tasks", "completed_work_units")
    op.drop_column("tasks", "total_work_units")
    op.drop_column("tasks", "max_concurrency")
    op.drop_column("tasks", "min_concurrency")
