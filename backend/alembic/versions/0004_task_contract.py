"""unify task contract: add title/description/docker_image/command/env_vars/required_tflops

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-24 00:30:00

"""
import sqlalchemy as sa

from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'tasks',
        sa.Column('title', sa.String(128), nullable=False, server_default=''),
    )
    op.add_column('tasks', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('tasks', sa.Column('docker_image', sa.String(256), nullable=True))
    op.add_column('tasks', sa.Column('command', sa.Text(), nullable=True))
    op.add_column('tasks', sa.Column('env_vars_json', sa.Text(), nullable=True))
    op.add_column(
        'tasks',
        sa.Column('required_tflops', sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('tasks', 'required_tflops')
    op.drop_column('tasks', 'env_vars_json')
    op.drop_column('tasks', 'command')
    op.drop_column('tasks', 'docker_image')
    op.drop_column('tasks', 'description')
    op.drop_column('tasks', 'title')
