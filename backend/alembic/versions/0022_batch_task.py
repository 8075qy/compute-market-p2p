"""add batch task columns for work-unit sharding

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-24 23:59:00

批处理任务（08 文档 4.1）：
- tasktype 枚举新增 'BATCH' 值
- tasks.input_file_key / input_file_size：输入数据包（zip）
- tasks.batch_size：每批工作项数，0 = 系统自动
- task_executions.work_unit_start / work_unit_end：该执行负责的工作项半开区间 [start, end)

命名说明：模型 `Enum(TaskType)` 未指定 name，`create_all` 生成的原生枚举名为 `tasktype`；
alembic 0001 曾用 `task_type`，两者不一致为既有技术债，此处按实际存在的类型名加值。
SQLAlchemy 持久化枚举成员名（大写），故新增值须为 'BATCH' 而非 'batch'。
"""

import sqlalchemy as sa

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 模型 Enum(TaskType) 未指定 name，create_all 生成的原生枚举名为 tasktype；
    # SQLAlchemy 持久化枚举成员名（大写），故新增值须为 'BATCH' 而非 'batch'
    op.execute(sa.text("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'BATCH'"))
    op.add_column("tasks", sa.Column("input_file_key", sa.String(256), nullable=True))
    op.add_column("tasks", sa.Column("input_file_size", sa.BigInteger(), nullable=True))
    op.add_column(
        "tasks", sa.Column("batch_size", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(
        "task_executions", sa.Column("work_unit_start", sa.Integer(), nullable=True)
    )
    op.add_column(
        "task_executions", sa.Column("work_unit_end", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("task_executions", "work_unit_end")
    op.drop_column("task_executions", "work_unit_start")
    op.drop_column("tasks", "batch_size")
    op.drop_column("tasks", "input_file_size")
    op.drop_column("tasks", "input_file_key")
    # 注意：PostgreSQL 不支持从原生 enum 删除值，'batch' 保留，避免破坏存量数据
