"""add_phase8_field_ops_and_feedback

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-02 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Add resolution columns to complaints if not present
    complaint_columns = [col['name'] for col in inspector.get_columns('complaints')]
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        if 'resolution_note' not in complaint_columns:
            batch_op.add_column(sa.Column('resolution_note', sa.Text(), nullable=True))
        if 'resolution_image_path' not in complaint_columns:
            batch_op.add_column(sa.Column('resolution_image_path', sa.String(length=255), nullable=True))
        if 'resolution_submitted_at' not in complaint_columns:
            batch_op.add_column(sa.Column('resolution_submitted_at', sa.DateTime(), nullable=True))
        if 'resolved_at' not in complaint_columns:
            batch_op.add_column(sa.Column('resolved_at', sa.DateTime(), nullable=True))

    # 2. Create citizen_feedback table if not present
    if 'citizen_feedback' not in tables:
        op.create_table(
            'citizen_feedback',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('complaint_id', sa.String(length=8), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('result', sa.String(length=32), nullable=False),
            sa.Column('comment', sa.Text(), nullable=True),
            sa.Column('image_path', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        with op.batch_alter_table('citizen_feedback', schema=None) as batch_op:
            batch_op.create_index('ix_citizen_feedback_complaint_id', ['complaint_id'], unique=False)
            batch_op.create_index('ix_citizen_feedback_user_id', ['user_id'], unique=False)
            batch_op.create_index('ix_citizen_feedback_result', ['result'], unique=False)
            batch_op.create_index('ix_citizen_feedback_created_at', ['created_at'], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if 'citizen_feedback' in tables:
        op.drop_table('citizen_feedback')

    complaint_columns = [col['name'] for col in inspector.get_columns('complaints')]
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        if 'resolved_at' in complaint_columns:
            batch_op.drop_column('resolved_at')
        if 'resolution_submitted_at' in complaint_columns:
            batch_op.drop_column('resolution_submitted_at')
        if 'resolution_image_path' in complaint_columns:
            batch_op.drop_column('resolution_image_path')
        if 'resolution_note' in complaint_columns:
            batch_op.drop_column('resolution_note')
