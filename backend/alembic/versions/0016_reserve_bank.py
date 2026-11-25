"""add reserve interest allocations and borrow records

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-24 23:30:00

算力时间银行闭环：
- reserve_interest_allocations：每轮利息分配给单账户的明细，支撑「利息明细」查询
- reserve_borrow_records：用户取用储备分转为自由分的流水，支撑「借用/取用」功能与上限管控
"""

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reserve_interest_allocations",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("record_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("reserve_points_before", sa.BigInteger(), nullable=False),
        sa.Column("interest_points", sa.BigInteger(), nullable=False),
        sa.Column(
            "distributed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["record_id"], ["reserve_interest_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reserve_interest_allocations_record",
        "reserve_interest_allocations",
        ["record_id"],
        unique=False,
    )
    op.create_index(
        "ix_reserve_interest_allocations_user",
        "reserve_interest_allocations",
        ["user_id", "distributed_at"],
        unique=False,
    )

    op.create_table(
        "reserve_borrow_records",
        sa.Column("id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_points", sa.BigInteger(), nullable=False),
        sa.Column("balance_before", sa.BigInteger(), nullable=False),
        sa.Column("reserve_before", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reserve_borrow_records_user",
        "reserve_borrow_records",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reserve_borrow_records_user", table_name="reserve_borrow_records")
    op.drop_table("reserve_borrow_records")
    op.drop_index(
        "ix_reserve_interest_allocations_user",
        table_name="reserve_interest_allocations",
    )
    op.drop_index(
        "ix_reserve_interest_allocations_record",
        table_name="reserve_interest_allocations",
    )
    op.drop_table("reserve_interest_allocations")
