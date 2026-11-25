"""add nodes.gpu_count for multi-GPU node support

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-24 23:55:00

多卡节点接入（07 文档 4.1）：
- nodes.gpu_count：节点 GPU 卡数，默认 1（单卡），整机总显存 = vram_gb × gpu_count
- 存量节点自动回填为 1，向后兼容
"""

import sqlalchemy as sa

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "nodes",
        sa.Column("gpu_count", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("nodes", "gpu_count")
