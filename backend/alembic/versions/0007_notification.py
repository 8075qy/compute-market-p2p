"""add notifications table

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-24 03:00:00

"""
import sqlalchemy as sa

from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    notification_type = sa.Enum(
        'task_completed', 'task_failed', 'settlement_paid', 'system',
        name='notification_type',
    )
    notification_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'notifications',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('type', notification_type, nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('ref_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_type', 'notifications', ['type'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'is_read'])


def downgrade() -> None:
    op.drop_index('ix_notifications_user_read', table_name='notifications')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_type', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_table('notifications')
    sa.Enum(name='notification_type').drop(op.get_bind(), checkfirst=True)
