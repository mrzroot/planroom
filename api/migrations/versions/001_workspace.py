import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None


def upgrade():
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("plan", sa.JSON, nullable=True),
        sa.Column("questionnaire", sa.JSON, nullable=True),
    )
    op.create_table(
        "sessions",
        sa.Column("digest", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])


def downgrade():
    op.drop_table("sessions")
    op.drop_table("accounts")
