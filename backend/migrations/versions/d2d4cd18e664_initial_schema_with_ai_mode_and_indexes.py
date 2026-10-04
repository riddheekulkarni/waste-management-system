"""initial_schema_with_ai_mode_and_indexes

Revision ID: d2d4cd18e664
Revises: 
Create Date: 2026-10-02 15:07:37.734127

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2d4cd18e664'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Users Table
    if 'users' not in tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('username', sa.String(length=80), nullable=False),
            sa.Column('email', sa.String(length=120), nullable=False),
            sa.Column('password_hash', sa.String(length=256), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False, server_default='citizen'),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email'),
            sa.UniqueConstraint('username')
        )

    # 2. Complaints Table
    if 'complaints' not in tables:
        op.create_table(
            'complaints',
            sa.Column('id', sa.String(length=8), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('image_path', sa.String(length=255), nullable=True),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column('latitude', sa.Float(), nullable=True),
            sa.Column('longitude', sa.Float(), nullable=True),
            sa.Column('severity_level', sa.String(length=10), nullable=True),
            sa.Column('coverage_ratio', sa.Float(), nullable=True),
            sa.Column('item_count', sa.Integer(), nullable=True),
            sa.Column('department', sa.String(length=64), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=True, server_default='Open'),
            sa.Column('is_duplicate', sa.Boolean(), nullable=True, server_default='0'),
            sa.Column('duplicate_of_id', sa.String(length=8), nullable=True),
            sa.Column('ai_mode', sa.String(length=20), nullable=True, server_default='MOCK_DEMO'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
    else:
        # Verify columns exist on existing table
        columns = [c['name'] for c in inspector.get_columns('complaints')]
        with op.batch_alter_table('complaints', schema=None) as batch_op:
            if 'ai_mode' not in columns:
                batch_op.add_column(sa.Column('ai_mode', sa.String(length=20), server_default='MOCK_DEMO', nullable=True))
            if 'is_duplicate' not in columns:
                batch_op.add_column(sa.Column('is_duplicate', sa.Boolean(), server_default='0', nullable=True))
            if 'duplicate_of_id' not in columns:
                batch_op.add_column(sa.Column('duplicate_of_id', sa.String(length=8), nullable=True))

    # 3. Detection Items Table
    if 'detection_items' not in tables:
        op.create_table(
            'detection_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('complaint_id', sa.String(length=8), nullable=False),
            sa.Column('cls', sa.String(length=50), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('x1', sa.Float(), nullable=True),
            sa.Column('y1', sa.Float(), nullable=True),
            sa.Column('x2', sa.Float(), nullable=True),
            sa.Column('y2', sa.Float(), nullable=True),
            sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id']),
            sa.PrimaryKeyConstraint('id')
        )

    # 4. Indexes (Complaints)
    existing_complaint_indexes = [idx['name'] for idx in inspector.get_indexes('complaints')]
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        if 'idx_complaints_lat_lng' not in existing_complaint_indexes:
            batch_op.create_index('idx_complaints_lat_lng', ['latitude', 'longitude'], unique=False)
        if 'ix_complaints_created_at' not in existing_complaint_indexes:
            batch_op.create_index('ix_complaints_created_at', ['created_at'], unique=False)
        if 'ix_complaints_department' not in existing_complaint_indexes:
            batch_op.create_index('ix_complaints_department', ['department'], unique=False)
        if 'ix_complaints_is_duplicate' not in existing_complaint_indexes:
            batch_op.create_index('ix_complaints_is_duplicate', ['is_duplicate'], unique=False)
        if 'ix_complaints_status' not in existing_complaint_indexes:
            batch_op.create_index('ix_complaints_status', ['status'], unique=False)
        if 'ix_complaints_user_id' not in existing_complaint_indexes:
            batch_op.create_index('ix_complaints_user_id', ['user_id'], unique=False)

    # 5. Indexes (Detection Items)
    existing_det_indexes = [idx['name'] for idx in inspector.get_indexes('detection_items')]
    with op.batch_alter_table('detection_items', schema=None) as batch_op:
        if 'ix_detection_items_cls' not in existing_det_indexes:
            batch_op.create_index('ix_detection_items_cls', ['cls'], unique=False)
        if 'ix_detection_items_complaint_id' not in existing_det_indexes:
            batch_op.create_index('ix_detection_items_complaint_id', ['complaint_id'], unique=False)


def downgrade():
    with op.batch_alter_table('detection_items', schema=None) as batch_op:
        batch_op.drop_index('ix_detection_items_complaint_id')
        batch_op.drop_index('ix_detection_items_cls')

    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.drop_index('ix_complaints_user_id')
        batch_op.drop_index('ix_complaints_status')
        batch_op.drop_index('ix_complaints_is_duplicate')
        batch_op.drop_index('ix_complaints_department')
        batch_op.drop_index('ix_complaints_created_at')
        batch_op.drop_index('idx_complaints_lat_lng')

    op.drop_table('detection_items')
    op.drop_table('complaints')
    op.drop_table('users')
