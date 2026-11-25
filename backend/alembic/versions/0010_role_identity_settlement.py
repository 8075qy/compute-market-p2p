"""rework roles into user identity and settlement direction

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-24 18:00:00

将「用户身份」与「结算方向」解耦：
- 用户身份：user（供需一体，默认）/ admin（管理员，仅后台指定）
- 结算方向：supplier / demander（仅用于 settlements.role 标记）
- 存量 supplier/demander 账号统一归一为 user 身份，admin 保留
"""
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == 'postgresql':
        # 1. 结算方向改用独立的 settlement_role 枚举类型
        settlement_role = postgresql.ENUM(
            'supplier', 'demander', name='settlement_role', create_type=False
        )
        settlement_role.create(bind, checkfirst=True)
        op.execute(
            "ALTER TABLE settlements "
            "ALTER COLUMN role TYPE settlement_role "
            "USING role::text::settlement_role"
        )

        # 2. 存量用户身份归一：supplier/demander -> user，admin 保留
        op.execute(
            """
            UPDATE users
            SET roles = (
                SELECT COALESCE(jsonb_agg(DISTINCT CASE
                    WHEN elem IN ('supplier', 'demander') THEN 'user'
                    ELSE elem
                END), '[]'::jsonb)
                FROM jsonb_array_elements_text(roles::jsonb) AS elem
            )::json
            WHERE roles IS NOT NULL
            """
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == 'postgresql':
        op.execute(
            "ALTER TABLE settlements "
            "ALTER COLUMN role TYPE user_role "
            "USING role::text::user_role"
        )
        settlement_role = postgresql.ENUM(
            'supplier', 'demander', name='settlement_role', create_type=False
        )
        settlement_role.drop(bind, checkfirst=True)
