"""Initial local learning records.

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("challenge_progress", sa.Column("challenge_id", sa.String(80), primary_key=True), sa.Column("state", sa.String(30), nullable=False, server_default="available"), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("hint_level", sa.Integer(), nullable=False, server_default="0"), sa.Column("latest_feedback", sa.Text()))
    op.create_table("completion_history", sa.Column("id", sa.String(36), primary_key=True), sa.Column("challenge_id", sa.String(80), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("verification_json", sa.Text(), nullable=False))
    op.create_index("ix_completion_history_challenge_id", "completion_history", ["challenge_id"])
    op.create_table("achievements", sa.Column("id", sa.String(100), primary_key=True), sa.Column("title", sa.String(160), nullable=False), sa.Column("detail", sa.Text(), nullable=False), sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("notes", sa.Column("id", sa.String(36), primary_key=True), sa.Column("kind", sa.String(20), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("challenge_id", sa.String(80)), sa.Column("tags_json", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_notes_challenge_id", "notes", ["challenge_id"])
    op.create_table("preferences", sa.Column("key", sa.String(100), primary_key=True), sa.Column("value_json", sa.Text(), nullable=False))
    op.create_table("workspace_registry", sa.Column("challenge_id", sa.String(80), primary_key=True), sa.Column("container_name", sa.String(150), nullable=False, unique=True), sa.Column("volume_name", sa.String(150), nullable=False, unique=True), sa.Column("network_name", sa.String(150)), sa.Column("state", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("challenge_overrides", sa.Column("challenge_id", sa.String(80), primary_key=True), sa.Column("manifest_json", sa.Text(), nullable=False), sa.Column("disabled", sa.Boolean(), nullable=False), sa.Column("is_custom", sa.Boolean(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    op.drop_table("challenge_overrides")
    op.drop_table("workspace_registry")
    op.drop_table("preferences")
    op.drop_index("ix_notes_challenge_id", table_name="notes")
    op.drop_table("notes")
    op.drop_table("achievements")
    op.drop_index("ix_completion_history_challenge_id", table_name="completion_history")
    op.drop_table("completion_history")
    op.drop_table("challenge_progress")
