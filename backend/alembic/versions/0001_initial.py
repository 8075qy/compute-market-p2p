"""Initial migration

Revision ID: 0001
Revises:
Create Date: 2026-11-23 13:15:00

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建枚举类型
    user_role = sa.Enum('supplier', 'demander', 'admin', name='user_role')
    node_status = sa.Enum('online', 'offline', 'maintenance', name='node_status')
    task_status = sa.Enum('pending', 'scheduling', 'assigned', 'running', 'completed', 'failed', 'cancelled', name='task_status')
    task_type = sa.Enum('inference', 'training', name='task_type')
    settlement_status = sa.Enum('pending', 'settled', 'refunding', 'refunded', name='settlement_status')
    account_type = sa.Enum('alipay', 'wechat', 'bank', name='account_type')

    user_role.create(op.get_bind(), checkfirst=True)
    node_status.create(op.get_bind(), checkfirst=True)
    task_status.create(op.get_bind(), checkfirst=True)
    task_type.create(op.get_bind(), checkfirst=True)
    settlement_status.create(op.get_bind(), checkfirst=True)
    account_type.create(op.get_bind(), checkfirst=True)

    # 用户表
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False),
        sa.Column('email', sa.String(128), nullable=True),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('role', user_role, nullable=False, server_default='demander'),
        sa.Column('nickname', sa.String(64), nullable=True),
        sa.Column('avatar_url', sa.String(512), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('phone'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_phone', 'users', ['phone'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 积分账户表
    op.create_table(
        'accounts',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('balance_points', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('frozen_points', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_earned', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_spent', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('withdrawal_account_type', account_type, nullable=True),
        sa.Column('withdrawal_account_no', sa.String(64), nullable=True),
        sa.Column('withdrawal_account_name', sa.String(64), nullable=True),
        sa.Column('withdrawal_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id'),
    )

    # 节点表
    op.create_table(
        'nodes',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('gpu_model', sa.String(64), nullable=False),
        sa.Column('vram_gb', sa.Integer(), nullable=False),
        sa.Column('peak_tflops', sa.Numeric(10, 2), nullable=False),
        sa.Column('region_province', sa.String(32), nullable=False),
        sa.Column('region_city', sa.String(32), nullable=False),
        sa.Column('region_district', sa.String(32), nullable=True),
        sa.Column('status', node_status, nullable=False, server_default='offline'),
        sa.Column('is_online', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_tasks_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_points_earned', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('reputation_score', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('docker_image', sa.String(256), nullable=True),
        sa.Column('config_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_nodes_owner_status', 'nodes', ['owner_id', 'status'])
    op.create_index('ix_nodes_schedulable', 'nodes', ['is_online', 'status', 'vram_gb', 'peak_tflops'])
    op.create_index('ix_nodes_last_heartbeat', 'nodes', ['last_heartbeat_at'])

    # 任务表
    op.create_table(
        'tasks',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('task_no', sa.String(32), nullable=False),
        sa.Column('demander_id', UUID(as_uuid=True), nullable=False),
        sa.Column('type', task_type, nullable=False),
        sa.Column('model_source', sa.String(32), nullable=False),
        sa.Column('model_id', UUID(as_uuid=True), nullable=True),
        sa.Column('model_file_key', sa.String(256), nullable=True),
        sa.Column('model_file_size', sa.BigInteger(), nullable=True),
        sa.Column('params_json', sa.Text(), nullable=False),
        sa.Column('concurrency', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('timeout_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('required_vram_gb', sa.Integer(), nullable=False),
        sa.Column('budget_points', sa.BigInteger(), nullable=False),
        sa.Column('min_settlement_unit', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('status', task_status, nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('assigned_node_id', UUID(as_uuid=True), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_files_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['demander_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_node_id'], ['nodes.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('task_no'),
    )
    op.create_index('ix_tasks_task_no', 'tasks', ['task_no'], unique=True)
    op.create_index('ix_tasks_demander_status', 'tasks', ['demander_id', 'status'])
    op.create_index('ix_tasks_scheduling', 'tasks', ['status', 'created_at'])

    # 任务执行记录表
    op.create_table(
        'task_executions',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', UUID(as_uuid=True), nullable=False),
        sa.Column('node_id', UUID(as_uuid=True), nullable=False),
        sa.Column('attempt_no', sa.Integer(), nullable=False),
        sa.Column('status', task_status, nullable=False, server_default='assigned'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('compute_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('compute_points', sa.BigInteger(), nullable=True),
        sa.Column('platform_fee_rate', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('platform_fee_points', sa.BigInteger(), nullable=True),
        sa.Column('supplier_earnings_points', sa.BigInteger(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_log_key', sa.String(256), nullable=True),
        sa.Column('proof_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('task_id', 'attempt_no', name='uq_task_attempt'),
    )
    op.create_index('ix_task_executions_task_id', 'task_executions', ['task_id'])
    op.create_index('ix_task_executions_node_status', 'task_executions', ['node_id', 'status'])

    # 结算记录表
    op.create_table(
        'settlements',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('settlement_no', sa.String(32), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', UUID(as_uuid=True), nullable=False),
        sa.Column('role', user_role, nullable=False),
        sa.Column('compute_points', sa.BigInteger(), nullable=False),
        sa.Column('platform_fee_rate', sa.Integer(), nullable=False),
        sa.Column('platform_fee_points', sa.BigInteger(), nullable=False),
        sa.Column('net_points', sa.BigInteger(), nullable=False),
        sa.Column('destination_account', sa.String(64), nullable=False),
        sa.Column('status', settlement_status, nullable=False, server_default='pending'),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['execution_id'], ['task_executions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('settlement_no'),
    )
    op.create_index('ix_settlements_settlement_no', 'settlements', ['settlement_no'], unique=True)
    op.create_index('ix_settlements_user_status', 'settlements', ['user_id', 'status'])
    op.create_index('ix_settlements_task', 'settlements', ['task_id'])
    op.create_index('ix_settlements_execution', 'settlements', ['execution_id'])

    # 平台配置表
    op.create_table(
        'platform_config',
        sa.Column('id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('platform_fee_rate', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('min_settlement_unit', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('points_to_cny_rate', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_task_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('node_offline_threshold_minutes', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('task_scheduling_timeout_minutes', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('settlement_timeout_hours', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 审计日志表
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), nullable=False),
        sa.Column('prev_hash', sa.String(64), nullable=True),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('entity_type', sa.String(32), nullable=False),
        sa.Column('entity_id', UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hash'),
    )
    op.create_index('ix_audit_logs_chain', 'audit_logs', ['prev_hash'])
    op.create_index('ix_audit_logs_entity', 'audit_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('ix_audit_logs_entity', table_name='audit_logs')
    op.drop_index('ix_audit_logs_chain', table_name='audit_logs')
    op.drop_table('audit_logs')

    op.drop_table('platform_config')

    op.drop_index('ix_settlements_execution', table_name='settlements')
    op.drop_index('ix_settlements_task', table_name='settlements')
    op.drop_index('ix_settlements_user_status', table_name='settlements')
    op.drop_index('ix_settlements_settlement_no', table_name='settlements')
    op.drop_table('settlements')

    op.drop_index('ix_task_executions_node_status', table_name='task_executions')
    op.drop_index('ix_task_executions_task_id', table_name='task_executions')
    op.drop_table('task_executions')

    op.drop_index('ix_tasks_scheduling', table_name='tasks')
    op.drop_index('ix_tasks_demander_status', table_name='tasks')
    op.drop_index('ix_tasks_task_no', table_name='tasks')
    op.drop_table('tasks')

    op.drop_index('ix_nodes_last_heartbeat', table_name='nodes')
    op.drop_index('ix_nodes_schedulable', table_name='nodes')
    op.drop_index('ix_nodes_owner_status', table_name='nodes')
    op.drop_table('nodes')

    op.drop_table('accounts')

    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_phone', table_name='users')
    op.drop_table('users')

    # 删除枚举类型
    sa.Enum(name='account_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='settlement_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='task_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='task_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='node_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='user_role').drop(op.get_bind(), checkfirst=True)
