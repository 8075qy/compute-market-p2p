"""convert user single role to multiple roles

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-23 18:00:00

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增多角色列（JSON 数组），并把旧单值 role 迁移为单元素数组
    op.add_column(
        'users',
        sa.Column('roles', sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.execute("UPDATE users SET roles = json_build_array(role::text)")
    op.drop_column('users', 'role')
    # 注意：user_role 枚举类型仍被 settlements.role 使用，故不删除该类型


def downgrade() -> None:
    # 回滚：取 roles 第一个元素还原为单值 role（仅用于开发环境回退）
    user_role = postgresql.ENUM(
        'supplier', 'demander', 'admin', name='user_role', create_type=False
    )
    op.add_column(
        'users',
        sa.Column('role', user_role, nullable=False, server_default='demander'),
    )
    op.execute(
        "UPDATE users SET role = COALESCE(roles->>0, 'demander') "
        "WHERE json_array_length(roles) > 0"
    )
    op.drop_column('users', 'roles')
