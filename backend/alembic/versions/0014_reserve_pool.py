"""add reserve pool fields

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-24 22:00:00

算力互助网络「算力时间银行」第一阶段：
- accounts 增加 reserve_points 储备分（贡献算力时按准备金率锁定部分收益进全网储备池）
- platform_config 增加三个治理参数：reserve_ratio 准备金率、max_borrow_ratio 单人借用上限、reserve_interest_ratio 储备利息比例
- task_executions 增加 reserve_points 记录该执行拆分的储备分
"""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column(
            "reserve_points",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "reserve_ratio",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "max_borrow_ratio",
            sa.Integer(),
            nullable=False,
            server_default="20",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "reserve_interest_ratio",
            sa.Integer(),
            nullable=False,
            server_default="50",
        ),
    )
    op.add_column(
        "task_executions",
        sa.Column("reserve_points", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_executions", "reserve_points")
    op.drop_column("platform_config", "reserve_interest_ratio")
    op.drop_column("platform_config", "max_borrow_ratio")
    op.drop_column("platform_config", "reserve_ratio")
    op.drop_column("accounts", "reserve_points")
