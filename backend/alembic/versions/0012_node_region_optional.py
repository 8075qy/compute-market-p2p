"""make node region optional

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24 20:00:00

节点所在地区改为可选：不再要求手动填写，后期按 IP 动态获取。
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("nodes", "region_province", nullable=True)
    op.alter_column("nodes", "region_city", nullable=True)


def downgrade() -> None:
    op.alter_column("nodes", "region_province", nullable=False)
    op.alter_column("nodes", "region_city", nullable=False)
