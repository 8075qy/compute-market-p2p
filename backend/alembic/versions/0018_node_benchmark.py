"""add nodes benchmark columns for hardware capability verification

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-24 23:59:00

硬件谎报检测（P1-4）：
- benchmark_tflops：算力对标值（规格库标称 / agent 实测）
- benchmark_status：pending / verified / failed
- benchmarked_at：对标时间
"""

import sqlalchemy as sa

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    benchmark_status = sa.Enum("PENDING", "VERIFIED", "FAILED", name="benchmark_status")
    benchmark_status.create(op.get_bind(), checkfirst=True)
    op.add_column("nodes", sa.Column("benchmark_tflops", sa.Numeric(10, 2), nullable=True))
    op.add_column(
        "nodes",
        sa.Column(
            "benchmark_status",
            benchmark_status,
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column("nodes", sa.Column("benchmarked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("nodes", "benchmarked_at")
    op.drop_column("nodes", "benchmark_status")
    op.drop_column("nodes", "benchmark_tflops")
    sa.Enum(name="benchmark_status").drop(op.get_bind(), checkfirst=True)
