"""add task_executions.challenge_nonce for anti-replay

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-24 20:20:00

防重放（P0-3）：
- task_executions.challenge_nonce：每次执行唯一的随机挑战种子，绑定到 proof_hash，
  使结果无法跨次缓存复用（此列早前在模型中定义，但遗漏迁移，此处补齐）
"""

import sqlalchemy as sa

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "task_executions",
        sa.Column(
            "challenge_nonce",
            sa.String(length=32),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("task_executions", "challenge_nonce")
