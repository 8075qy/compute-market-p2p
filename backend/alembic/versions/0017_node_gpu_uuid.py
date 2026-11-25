"""add nodes.gpu_uuid for multi-open prevention

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-24 23:50:00

防多开（P1-5）：
- nodes.gpu_uuid：GPU 唯一标识（nvidia-smi 上报的 UUID），同一 UUID 限注册节点数
"""

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nodes", sa.Column("gpu_uuid", sa.String(length=128), nullable=True))
    op.create_index("ix_nodes_gpu_uuid", "nodes", ["gpu_uuid"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_nodes_gpu_uuid", table_name="nodes")
    op.drop_column("nodes", "gpu_uuid")
