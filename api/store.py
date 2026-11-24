import os
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

engine = create_engine(
    URL.create(
        "postgresql+psycopg",
        username="planroom",
        password=os.environ["POSTGRES_PASSWORD"],
        host="db",
        database="planroom",
    ),
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(Text)
    plan: Mapped[dict | None] = mapped_column(JSON)
    questionnaire: Mapped[dict | None] = mapped_column(JSON)


class LoginSession(Base):
    __tablename__ = "sessions"

    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
