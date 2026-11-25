"""add reserve interest records

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-24 23:00:00

算力时间银行第二阶段：新增储备利息分配记录表，用于记录每轮公共池产出返还快照并保证分配幂等。
"""

import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reserve_interest_records",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("cycle_output_points", sa.BigInteger(), nullable=False),
        sa.Column("interest_points", sa.BigInteger(), nullable=False),
        sa.Column("total_reserve_points", sa.BigInteger(), nullable=False),
        sa.Column(
            "distributed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reserve_interest_records_created",
        "reserve_interest_records",
        ["distributed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reserve_interest_records_created",
        table_name="reserve_interest_records",
    )
    op.drop_table("reserve_interest_records")
