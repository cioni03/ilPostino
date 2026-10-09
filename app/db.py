"""Database: engine, sessione e modelli ORM (SQLite)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from app.config import settings

settings.database_path_abs.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{settings.database_path_abs}", connect_args={"check_same_thread": False, "timeout": 10})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def db_session() -> Session:
    """Context manager transazionale: commit automatico, rollback su errore."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _now() -> datetime:
    return datetime.now()


class Base(DeclarativeBase):
    pass


class SmtpServer(Base):
    __tablename__ = "smtp_servers"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=587)
    security = Column(String(10), nullable=False, default="tls")  # tls | ssl | none
    username = Column(String(255))
    password = Column(String(255))  # in chiaro: il DB sta solo sul PC
    sender_email = Column(String(255), nullable=False)
    sender_name = Column(String(120))
    reply_to = Column(String(255))
    rate_limit_emails_per_hour = Column(Integer)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)


contact_group = Table(
    "contact_group",
    Base.metadata,
    Column("contact_id", Integer, ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    UniqueConstraint("contact_id", "group_id", name="uq_contact_group"),
)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    first_name = Column(String(120))
    last_name = Column(String(120))
    company = Column(String(160))
    tags = Column(String(255))
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    groups = relationship("Group", secondary=contact_group, back_populates="contacts")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    created_at = Column(DateTime, default=_now, nullable=False)

    contacts = relationship("Contact", secondary=contact_group, back_populates="groups")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    subject = Column(String(500), nullable=False, default="")
    html_body = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="running", index=True)
    # running | paused | scheduled | completed | cancelled

    smtp_server_id = Column(Integer, ForeignKey("smtp_servers.id", ondelete="SET NULL"))
    smtp_snapshot = Column(JSON, nullable=False)  # parametri immutabili al momento dell'invio
    template_id = Column(Integer, ForeignKey("email_templates.id", ondelete="SET NULL"))
    template_name = Column(String(120))
    subject = Column(String(500), nullable=False)  # snapshot template
    html_body = Column(Text, nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="SET NULL"))
    group_name = Column(String(120))

    total_count = Column(Integer, nullable=False, default=0)
    tranche_size = Column(Integer, nullable=False, default=50)
    pause_seconds = Column(Integer, nullable=False, default=60)
    max_retries = Column(Integer, nullable=False, default=3)
    retry_delay_seconds = Column(Integer, nullable=False, default=30)
    scheduled_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    auto_pause_reason = Column(Text)
    created_at = Column(DateTime, default=_now, nullable=False)


class SendItem(Base):
    __tablename__ = "send_items"
    __table_args__ = (Index("ix_send_items_campaign_status", "campaign_id", "status"),)

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    contact_id = Column(Integer)  # senza FK: il contatto può essere eliminato
    # snapshot destinatario (immutabile)
    email = Column(String(255), nullable=False)
    first_name = Column(String(120))
    last_name = Column(String(120))
    company = Column(String(160))
    tags = Column(String(255))
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    last_error = Column(Text)
    sent_at = Column(DateTime)


class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    level = Column(String(10), nullable=False, default="info")  # info|success|warning|error|critical
    message = Column(Text, nullable=False)
    detail = Column(Text)
    created_at = Column(DateTime, default=_now, nullable=False, index=True)
