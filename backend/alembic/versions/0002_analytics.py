"""Analytics tables — analytics_events, ocr_analytics, annotation_sessions

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-01 00:01:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'analytics_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('image_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('images.id', ondelete='SET NULL'), nullable=True),
        sa.Column('ocr_engine', sa.String(100), nullable=True),
        sa.Column('model_version', sa.String(100), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
    )
    op.create_index('ix_analytics_events_event_type', 'analytics_events', ['event_type'])
    op.create_index('ix_analytics_events_user_id', 'analytics_events', ['user_id'])
    op.create_index('ix_analytics_events_timestamp', 'analytics_events', ['timestamp'])

    op.create_table(
        'ocr_analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analytics_events.event_id', ondelete='CASCADE'), nullable=True, unique=True),
        sa.Column('image_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('images.id', ondelete='SET NULL'), nullable=True),
        sa.Column('processing_time', sa.Float, nullable=True),
        sa.Column('number_of_boxes', sa.Integer, nullable=True),
        sa.Column('average_confidence', sa.Float, nullable=True),
        sa.Column('accepted_boxes', sa.Integer, nullable=True),
        sa.Column('rejected_boxes', sa.Integer, nullable=True),
        sa.Column('corrected_boxes', sa.Integer, nullable=True),
        sa.Column('manual_boxes', sa.Integer, nullable=True),
        sa.Column('difficulty_score', sa.Float, nullable=True),
        sa.Column('failure_reason', sa.Text, nullable=True),
        sa.Column('image_width', sa.Integer, nullable=True),
        sa.Column('image_height', sa.Integer, nullable=True),
        sa.Column('orientation', sa.String(20), nullable=True),
        sa.Column('language', sa.String(50), nullable=True),
    )

    op.create_table(
        'annotation_sessions',
        sa.Column('session_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('image_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('images.id', ondelete='SET NULL'), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration', sa.Integer, nullable=True),
        sa.Column('annotations_created', sa.Integer, nullable=False, server_default='0'),
        sa.Column('annotations_corrected', sa.Integer, nullable=False, server_default='0'),
        sa.Column('annotations_deleted', sa.Integer, nullable=False, server_default='0'),
        sa.Column('zoom_operations', sa.Integer, nullable=False, server_default='0'),
        sa.Column('pan_operations', sa.Integer, nullable=False, server_default='0'),
        sa.Column('ocr_used', sa.Boolean, nullable=False, server_default='false'),
    )
    op.create_index('ix_annotation_sessions_user_id', 'annotation_sessions', ['user_id'])


def downgrade() -> None:
    op.drop_table('annotation_sessions')
    op.drop_table('ocr_analytics')
    op.drop_table('analytics_events')
