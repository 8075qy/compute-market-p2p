"""add users.username for first-run admin bootstrap

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-25 00:00:00

首次部署强制管理员初始化（用户名 + 密码）：
- users.username：管理员登录用户名（唯一，普通用户可为空）
- users.phone：由非空改为可空（管理员仅凭用户名注册，无手机号）
"""

import sqlalchemy as sa

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(64), nullable=True))
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.alter_column("users", "phone", existing_type=sa.String(20), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "phone", existing_type=sa.String(20), nullable=False)
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
