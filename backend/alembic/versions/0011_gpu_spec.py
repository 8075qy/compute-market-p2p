"""gpu specs reference table

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-24 19:00:00

新增 GPU 规格库表，预置常见型号的显存与峰值算力，减少节点登记手填。
"""

import json

import sqlalchemy as sa

from alembic import op
from app.services.gpu_spec import GPU_SPEC_SEED

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gpu_specs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gpu_model", sa.String(length=64), nullable=False),
        sa.Column("vendor", sa.String(length=16), nullable=False),
        sa.Column("vram_gb", sa.Integer(), nullable=False),
        sa.Column("peak_tflops", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("aliases_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gpu_model"),
    )
    op.create_index("ix_gpu_specs_gpu_model", "gpu_specs", ["gpu_model"], unique=True)

    # 预置规格数据（与 app.services.gpu_spec.GPU_SPEC_SEED 保持一致）
    table = sa.table(
        "gpu_specs",
        sa.column("gpu_model", sa.String),
        sa.column("vendor", sa.String),
        sa.column("vram_gb", sa.Integer),
        sa.column("peak_tflops", sa.Numeric),
        sa.column("aliases_json", sa.Text),
    )
    op.bulk_insert(
        table,
        [
            {
                "gpu_model": item["gpu_model"],
                "vendor": item["vendor"],
                "vram_gb": item["vram_gb"],
                "peak_tflops": item["peak_tflops"],
                "aliases_json": json.dumps(item["aliases"], ensure_ascii=False),
            }
            for item in GPU_SPEC_SEED
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_gpu_specs_gpu_model", table_name="gpu_specs")
    op.drop_table("gpu_specs")
