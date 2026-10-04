"""add_phase7_notifications

Revision ID: f6a7b8c9d0e1
Revises: e5c6a1b2c3d4
Create Date: 2026-10-02 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5c6a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'notifications' not in tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('ticket_id', sa.String(length=8), nullable=True),
            sa.Column('category', sa.String(length=32), nullable=False),
            sa.Column('title', sa.String(length=128), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('severity', sa.String(length=10), nullable=True),
            sa.Column('department', sa.String(length=64), nullable=True),
            sa.Column('is_read', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['ticket_id'], ['complaints.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('notifications', schema=None) as batch_op:
            batch_op.create_index('ix_notifications_user_id', ['user_id'], unique=False)
            batch_op.create_index('ix_notifications_ticket_id', ['ticket_id'], unique=False)
            batch_op.create_index('ix_notifications_category', ['category'], unique=False)
            batch_op.create_index('ix_notifications_is_read', ['is_read'], unique=False)
            batch_op.create_index('ix_notifications_created_at', ['created_at'], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if 'notifications' in tables:
        op.drop_table('notifications')
