"""remove withdrawal fields and CNY rate

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-24 21:00:00

删除账户表的提现相关字段与 account_type 枚举，并删除 platform_config 的积分换人民币汇率：
算力分仅用于纯对等交换，不再涉及提现/充值/变现。
"""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("accounts", "withdrawal_verified")
    op.drop_column("accounts", "withdrawal_account_name")
    op.drop_column("accounts", "withdrawal_account_no")
    op.drop_column("accounts", "withdrawal_account_type")
    sa.Enum(name="account_type").drop(op.get_bind(), checkfirst=True)
    op.drop_column("platform_config", "points_to_cny_rate")


def downgrade() -> None:
    account_type = sa.Enum("alipay", "wechat", "bank", name="account_type")
    account_type.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "accounts",
        sa.Column("withdrawal_account_type", account_type, nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("withdrawal_account_no", sa.String(64), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("withdrawal_account_name", sa.String(64), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "withdrawal_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "platform_config",
        sa.Column(
            "points_to_cny_rate",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
