"""add preauthorized billing (分段预授权 + 暂停恢复)

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-25 00:00:00

方案 C（10 文档）：实时扣款 + 暂停 + 恢复，采用分段预授权计费模型。
- taskstatus 枚举新增 'PAUSED' 值
- tasks.preauthorized_points：当前预授权（冻结）额度，替代旧的全额冻结语义
- 数据回填：对未终态任务（旧模型全额冻结），preauthorized_points = budget_points

命名说明：模型 `Enum(TaskStatus)` 未指定 name，`create_all` 生成的原生枚举名为
`taskstatus`（小写类名）；SQLAlchemy 持久化枚举成员名（大写），故新增值为 'PAUSED'。
"""

import sqlalchemy as sa

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'PAUSED'"))
    op.add_column(
        "tasks",
        sa.Column(
            "preauthorized_points",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    # 旧模型对未终态任务全额冻结预算；回填预授权额度为预算，避免收尾退款为 0 导致账实不符
    op.execute(
        sa.text(
            "UPDATE tasks SET preauthorized_points = budget_points "
            "WHERE status IN ('PENDING', 'SCHEDULING', 'ASSIGNED', 'RUNNING')"
        )
    )


def downgrade() -> None:
    op.drop_column("tasks", "preauthorized_points")
    # 注意：PostgreSQL 不支持从原生 enum 删除值，'PAUSED' 保留，避免破坏存量数据
