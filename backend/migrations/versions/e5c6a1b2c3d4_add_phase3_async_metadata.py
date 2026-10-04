"""add_phase3_async_metadata

Revision ID: e5c6a1b2c3d4
Revises: d2d4cd18e664
Create Date: 2026-10-02 15:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5c6a1b2c3d4'
down_revision = 'd2d4cd18e664'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {c['name'] for c in inspector.get_columns('complaints')}

    # Defensive addition of Phase 3 async processing metadata columns
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        if 'processing_status' not in existing_cols:
            batch_op.add_column(sa.Column('processing_status', sa.String(length=32), nullable=True, server_default='QUEUED'))
        if 'processing_started_at' not in existing_cols:
            batch_op.add_column(sa.Column('processing_started_at', sa.DateTime(), nullable=True))
        if 'processing_completed_at' not in existing_cols:
            batch_op.add_column(sa.Column('processing_completed_at', sa.DateTime(), nullable=True))
        if 'processing_duration_ms' not in existing_cols:
            batch_op.add_column(sa.Column('processing_duration_ms', sa.Integer(), nullable=True))
        if 'processing_error' not in existing_cols:
            batch_op.add_column(sa.Column('processing_error', sa.String(length=255), nullable=True))
        if 'model_name' not in existing_cols:
            batch_op.add_column(sa.Column('model_name', sa.String(length=64), nullable=True))
        if 'model_version' not in existing_cols:
            batch_op.add_column(sa.Column('model_version', sa.String(length=32), nullable=True))
        if 'retry_count' not in existing_cols:
            batch_op.add_column(sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))

    # Check and add index on processing_status
    indexes = {idx['name'] for idx in inspector.get_indexes('complaints')}
    if 'idx_complaints_proc_status' not in indexes:
        with op.batch_alter_table('complaints', schema=None) as batch_op:
            batch_op.create_index('idx_complaints_proc_status', ['processing_status'], unique=False)


def downgrade():
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.drop_index('idx_complaints_proc_status')
        batch_op.drop_column('retry_count')
        batch_op.drop_column('model_version')
        batch_op.drop_column('model_name')
        batch_op.drop_column('processing_error')
        batch_op.drop_column('processing_duration_ms')
        batch_op.drop_column('processing_completed_at')
        batch_op.drop_column('processing_started_at')
        batch_op.drop_column('processing_status')
