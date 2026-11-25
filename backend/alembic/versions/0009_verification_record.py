"""add verification records and sampling config

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-24 12:00:00

"""
import sqlalchemy as sa

from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # 结算状态新增「已回滚」，用于作弊复核失败后的结算追回
    if bind.dialect.name == 'postgresql':
        op.execute(
            sa.text("ALTER TYPE settlement_status ADD VALUE IF NOT EXISTS 'reversed'")
        )

    verification_status = sa.Enum(
        'pending', 'verified', 'failed', name='verification_status',
    )
    verification_status.create(bind, checkfirst=True)

    op.create_table(
        'verification_records',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('status', verification_status, nullable=False, server_default='pending'),
        sa.Column('expected_hash', sa.String(length=64), nullable=True),
        sa.Column('actual_hash', sa.String(length=64), nullable=True),
        sa.Column('result_files_json', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['execution_id'], ['task_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_verification_records_execution_id', 'verification_records', ['execution_id'])
    op.create_index('ix_verification_records_task_id', 'verification_records', ['task_id'])
    op.create_index('ix_verification_records_status', 'verification_records', ['status', 'created_at'])

    op.add_column(
        'platform_config',
        sa.Column('verification_sample_rate', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('platform_config', 'verification_sample_rate')
    op.drop_index('ix_verification_records_status', table_name='verification_records')
    op.drop_index('ix_verification_records_task_id', table_name='verification_records')
    op.drop_index('ix_verification_records_execution_id', table_name='verification_records')
    op.drop_table('verification_records')
    sa.Enum(name='verification_status').drop(op.get_bind(), checkfirst=True)
    # PostgreSQL 不支持删除枚举值，settlement_status 的 reversed 值在回滚时保留
