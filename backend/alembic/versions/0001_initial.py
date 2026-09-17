"""Initial schema — users, projects, images, annotations, refresh_tokens

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.Text, nullable=True),
        sa.Column('avatar_url', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('analytics_opt_out', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('role', sa.String(50), nullable=False, server_default='annotator'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'])

    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('default_language', sa.String(50), nullable=False, server_default='Marathi'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_projects_user_id', 'projects', ['user_id'])

    op.create_table(
        'images',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(512), nullable=False),
        sa.Column('storage_key', sa.Text, nullable=False),
        sa.Column('width', sa.Integer, nullable=False),
        sa.Column('height', sa.Integer, nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='Uploaded'),
        sa.Column('upload_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_images_project_id', 'images', ['project_id'])

    op.create_table(
        'annotations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('image_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('images.id', ondelete='CASCADE'), nullable=False),
        sa.Column('x1', sa.Float, nullable=False),
        sa.Column('y1', sa.Float, nullable=False),
        sa.Column('x2', sa.Float, nullable=False),
        sa.Column('y2', sa.Float, nullable=False),
        sa.Column('text', sa.Text, nullable=False, server_default=''),
        sa.Column('label', sa.String(50), nullable=False, server_default='Marathi'),
        sa.Column('confidence', sa.Float, nullable=False, server_default='1.0'),
        sa.Column('accepted', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('ocr_generated', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_corrected', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_annotations_image_id', 'annotations', ['image_id'])

    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])


def downgrade() -> None:
    op.drop_table('refresh_tokens')
    op.drop_table('annotations')
    op.drop_table('images')
    op.drop_table('projects')
    op.drop_table('users')
