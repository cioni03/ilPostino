"""Livello servizi: tutte le operazioni DB usate da UI e worker."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

from sqlalchemy import delete, func, select, update

from app.db import LogEntry, SendItem, Campaign, Contact, EmailTemplate, Group, SmtpServer, contact_group, db_session

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

DEFAULT_SEND = {"tranche_size": 50, "pause_seconds": 60, "max_retries": 3, "retry_delay": 30, "error_threshold": 8}


# ---------------------------------------------------------------- Server SMTP

def list_smtp(active_only: bool = False) -> list[SmtpServer]:
    with db_session() as db:
        stmt = select(SmtpServer).order_by(SmtpServer.name)
        if active_only:
            stmt = stmt.where(SmtpServer.active.is_(True))
        return list(db.execute(stmt).scalars().all())


def get_smtp(server_id: int) -> SmtpServer | None:
    with db_session() as db:
        return db.get(SmtpServer, server_id)


def save_smtp(
    server_id: int | None, *, name: str, host: str, port: int, security: str,
    username: str | None = "", password: str | None = "", sender_email: str, sender_name: str | None = "",
    reply_to: str | None = "", rate_limit: int = 0, active: bool = True,
) -> SmtpServer:
    if not EMAIL_RE.match(sender_email or ""):
        raise ValueError(f"Mittente non valido: {sender_email!r}")
    with db_session() as db:
        server = db.get(SmtpServer, server_id) if server_id else SmtpServer()
        if server_id and server is None:
            raise ValueError("Server SMTP non trovato")
        server.name, server.host, server.port, server.security = name.strip(), host.strip(), port, security
        server.username = (username or "").strip() or None
        if password:  # vuoto in modifica = mantieni l'attuale
            server.password = password
        server.sender_email = sender_email.strip().lower()
        server.sender_name = (sender_name or "").strip() or None
        server.reply_to = (reply_to or "").strip().lower() or None
        server.rate_limit_emails_per_hour = rate_limit or None
        server.active = active
        if not server_id:
            db.add(server)
        db.flush()
        return server


def duplicate_smtp(server_id: int) -> SmtpServer:
    with db_session() as db:
        src = db.get(SmtpServer, server_id)
        if src is None:
            raise ValueError("Server SMTP non trovato")
        copy = SmtpServer(**{c: getattr(src, c) for c in (
            "host", "port", "security", "username", "password", "sender_email",
            "sender_name", "reply_to", "rate_limit_emails_per_hour",
        )})
        copy.name, copy.active = f"{src.name} (copia)", False
        db.add(copy)
        db.flush()
        return copy


def delete_smtp(server_id: int) -> None:
    with db_session() as db:
        db.execute(delete(SmtpServer).where(SmtpServer.id == server_id))


def set_smtp_active(server_id: int, active: bool) -> None:
    with db_session() as db:
        server = db.get(SmtpServer, server_id)
        if server:
            server.active = active


# ---------------------------------------------------------------- Gruppi

def list_groups() -> list[dict]:
    with db_session() as db:
        groups = db.execute(select(Group).order_by(Group.name)).scalars().all()
        return [
            {
                "id": g.id,
                "name": g.name,
                "total": db.execute(
                    select(func.count(contact_group.c.contact_id)).where(contact_group.c.group_id == g.id)
                ).scalar_one(),
            }
            for g in groups
        ]


def create_group(name: str) -> Group:
    name = (name or "").strip()
    if not name:
        raise ValueError("Inserisci il nome del gruppo")
    with db_session() as db:
        if db.execute(select(Group).where(Group.name == name.strip())).scalar_one_or_none():
            raise ValueError(f"Il gruppo «{name}» esiste già")
        group = Group(name=name.strip())
        db.add(group)
        db.flush()
        return group


def delete_group(group_id: int) -> None:
    with db_session() as db:
        db.execute(delete(contact_group).where(contact_group.c.group_id == group_id))
        db.execute(delete(Group).where(Group.id == group_id))


def group_contacts(group_id: int) -> list[dict]:
    """Snapshot di tutti i contatti del gruppo: senza regole, tutti validi."""
    with db_session() as db:
        rows = db.execute(
            select(Contact)
            .join(contact_group, contact_group.c.contact_id == Contact.id)
            .where(contact_group.c.group_id == group_id)
            .order_by(Contact.id)
        ).scalars().all()
        return [
            {
                "contact_id": c.id, "email": c.email, "first_name": c.first_name,
                "last_name": c.last_name, "company": c.company, "tags": c.tags,
            }
            for c in rows
        ]


# ---------------------------------------------------------------- Contatti

def list_contacts(group_id: int | None = None, search: str = "", page: int = 1, per_page: int = 15):
    with db_session() as db:
        stmt = select(Contact)
        if group_id is not None:
            stmt = stmt.join(contact_group, contact_group.c.contact_id == Contact.id).where(
                contact_group.c.group_id == group_id
            )
        if search:
            like = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                func.lower(Contact.email).like(like)
                | func.lower(func.coalesce(Contact.first_name, "")).like(like)
                | func.lower(func.coalesce(Contact.last_name, "")).like(like)
                | func.lower(func.coalesce(Contact.company, "")).like(like)
            )
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = db.execute(stmt.order_by(Contact.email).offset((page - 1) * per_page).limit(per_page)).scalars().all()
        result = [
            {
                "id": c.id, "email": c.email, "first_name": c.first_name or "", "last_name": c.last_name or "",
                "company": c.company or "", "tags": c.tags or "",
                "groups": ", ".join(g.name for g in c.groups),
            }
            for c in rows
        ]
        return result, total


def save_contact(
    contact_id: int | None, *, email: str, first_name: str = "", last_name: str = "",
    company: str = "", tags: str = "", group_ids: list[int] | None = None,
    new_group_name: str = "",
) -> Contact:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError(f"Email non valida: {email!r}")
    with db_session() as db:
        existing = db.execute(select(Contact).where(Contact.email == email)).scalar_one_or_none()
        if existing is not None and existing.id != contact_id:
            raise ValueError(f"Esiste già un contatto con l'email {email}")
        contact = db.get(Contact, contact_id) if contact_id else Contact(email=email)
        if contact_id and contact is None:
            raise ValueError("Contatto non trovato")
        groups = list(contact.groups) if contact_id and group_ids is None else []
        if group_ids is not None:
            groups = list(db.execute(select(Group).where(Group.id.in_(group_ids))).scalars().all())
            if len(groups) != len(set(group_ids)):
                raise ValueError("Uno dei gruppi selezionati non esiste più")
        new_group_name = (new_group_name or "").strip()
        if new_group_name:
            if db.execute(select(Group).where(Group.name == new_group_name)).scalar_one_or_none():
                raise ValueError(f"Il gruppo «{new_group_name}» esiste già: selezionalo dall'elenco")
            group = Group(name=new_group_name)
            db.add(group)
            groups.append(group)
        if not groups:
            raise ValueError("Assegna il destinatario ad almeno un gruppo")
        contact.first_name = (first_name or "").strip() or None
        contact.last_name = (last_name or "").strip() or None
        contact.company = (company or "").strip() or None
        contact.tags = (tags or "").strip() or None
        contact.groups = groups
        if not contact_id:
            db.add(contact)
        db.flush()
        return contact


def delete_contact(contact_id: int) -> None:
    with db_session() as db:
        db.execute(delete(contact_group).where(contact_group.c.contact_id == contact_id))
        db.execute(delete(Contact).where(Contact.id == contact_id))


def import_pasted_csv(text: str, group_id: int | None, new_group_name: str = "") -> dict:
    """Import semplice: una riga per contatto con email;nome;cognome;azienda;tag.

    Delimiter auto (`,` `;` o tab), prima riga scartata se contiene «email»,
    righe senza email valida o duplicate vengono saltate senza fermarsi.
    """
    created = skipped = 0
    with db_session() as db:
        group = None
        if group_id:
            group = db.get(Group, group_id)
        elif (new_group_name or "").strip():
            name = new_group_name.strip()
            group = db.execute(select(Group).where(Group.name == name)).scalar_one_or_none()
            if group is None:
                group = Group(name=name)
                db.add(group)
                db.flush()
        if group is None:
            raise ValueError("Seleziona un gruppo esistente o inserisci il nome di un nuovo gruppo")
        lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
        if lines and "email" in lines[0].lower():
            lines = lines[1:]  # header
        for line in lines:
            parts = [p.strip() for p in re.split(r"[;,\t]", line)]
            email = next((p.lower() for p in parts if EMAIL_RE.match(p)), "")
            if not email:
                skipped += 1
                continue
            contact = db.execute(select(Contact).where(Contact.email == email)).scalar_one_or_none()
            if contact is None:
                others = [p for p in parts if p.lower() != email]
                contact = Contact(
                    email=email,
                    first_name=others[0] if others else None,
                    last_name=others[1] if len(others) > 1 else None,
                    company=others[2] if len(others) > 2 else None,
                    tags=others[3] if len(others) > 3 else None,
                )
                db.add(contact)
                db.flush()
                created += 1
            else:
                skipped += 1
            if group is not None and group not in contact.groups:
                contact.groups.append(group)
    return {"created": created, "skipped": skipped, "group": group.name if group else ""}


def export_contacts_csv() -> str:
    rows, _ = list_contacts(per_page=1_000_000)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["email", "nome", "cognome", "azienda", "tag", "gruppi"])
    for r in rows:
        writer.writerow([r["email"], r["first_name"], r["last_name"], r["company"], r["tags"], r["groups"]])
    return buf.getvalue()


# ---------------------------------------------------------------- Template

def list_templates() -> list[EmailTemplate]:
    with db_session() as db:
        return list(db.execute(select(EmailTemplate).order_by(EmailTemplate.name)).scalars().all())


def get_template(template_id: int) -> EmailTemplate | None:
    with db_session() as db:
        return db.get(EmailTemplate, template_id)


def save_template(template_id: int | None, *, name: str, subject: str, html_body: str) -> EmailTemplate:
    with db_session() as db:
        template = db.get(EmailTemplate, template_id) if template_id else EmailTemplate()
        if template_id and template is None:
            raise ValueError("Template non trovato")
        template.name = name.strip() or "Senza nome"
        template.subject = subject
        template.html_body = html_body
        if not template_id:
            db.add(template)
        db.flush()
        return template


def duplicate_template(template_id: int) -> EmailTemplate:
    with db_session() as db:
        src = db.get(EmailTemplate, template_id)
        if src is None:
            raise ValueError("Template non trovato")
        copy = EmailTemplate(name=f"{src.name} (copia)", subject=src.subject, html_body=src.html_body)
        db.add(copy)
        db.flush()
        return copy


def delete_template(template_id: int) -> None:
    with db_session() as db:
        db.execute(delete(EmailTemplate).where(EmailTemplate.id == template_id))


# ---------------------------------------------------------------- Campagne

def create_campaign(*, name: str, smtp_server_id: int, template_id: int | None, template_name: str,
                    subject: str, html_body: str, group_id: int, group_name: str,
                    tranche_size: int, pause_seconds: int, max_retries: int,
                    retry_delay_seconds: int, scheduled_at: datetime | None = None) -> Campaign:
    from app import templating

    with db_session() as db:
        server = db.get(SmtpServer, smtp_server_id)
        group = db.get(Group, group_id)
        if server is None or not server.active:
            raise ValueError("Server SMTP non trovato o non attivo")
        if group is None:
            raise ValueError("Gruppo non trovato")
        recipients = group_contacts(group.id)
        if not recipients:
            raise ValueError("Il gruppo selezionato non ha contatti")
        try:
            templating.render(subject, templating.SAMPLE_CONTEXT)
            templating.render(html_body, templating.SAMPLE_CONTEXT)
        except templating.TemplateError as e:
            raise ValueError(f"Errore nel template: {e}") from e

        now = datetime.now()
        scheduled = scheduled_at is not None and scheduled_at > now
        campaign = Campaign(
            name=name.strip(),
            status="scheduled" if scheduled else "running",
            smtp_server_id=server.id,
            smtp_snapshot={c: getattr(server, c) for c in (
                "name", "host", "port", "security", "username", "password",
                "sender_email", "sender_name", "reply_to", "rate_limit_emails_per_hour",
            )},
            template_id=template_id,
            template_name=template_name,
            subject=subject,
            html_body=html_body,
            group_id=group.id,
            group_name=group.name,
            total_count=len(recipients),
            tranche_size=tranche_size,
            pause_seconds=pause_seconds,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            scheduled_at=scheduled_at if scheduled else None,
            started_at=None if scheduled else now,
        )
        db.add(campaign)
        db.flush()
        db.add_all(
            SendItem(campaign_id=campaign.id, **r) for r in recipients
        )
        db.add(LogEntry(campaign_id=campaign.id, level="info",
                        message=f"Invio creato: {len(recipients)} destinatari, tranche da {tranche_size}, pausa {pause_seconds}s"))
        return campaign


def get_campaign(campaign_id: int) -> Campaign | None:
    with db_session() as db:
        return db.get(Campaign, campaign_id)


def list_campaigns(limit: int = 100) -> list[Campaign]:
    with db_session() as db:
        return list(db.execute(select(Campaign).order_by(Campaign.id.desc()).limit(limit)).scalars().all())


def status_counts(campaign_id: int) -> dict[str, int]:
    with db_session() as db:
        rows = db.execute(
            select(SendItem.status, func.count(SendItem.id)).where(SendItem.campaign_id == campaign_id).group_by(SendItem.status)
        ).all()
    counts = {s: 0 for s in ("pending", "processing", "sent", "failed_temp", "failed_perm", "skipped", "cancelled")}
    counts.update(dict(rows))
    return counts


def set_campaign_status(campaign_id: int, status: str, *, started: bool = False, completed: bool = False,
                        reason: str | None = None, log_message: str | None = None, log_level: str = "info") -> None:
    with db_session() as db:
        c = db.get(Campaign, campaign_id)
        if c is None:
            return
        c.status = status
        if started and c.started_at is None:
            c.started_at = datetime.now()
        if completed:
            c.completed_at = datetime.now()
        if reason is not None:
            c.auto_pause_reason = reason
        if log_message:
            db.add(LogEntry(campaign_id=campaign_id, level=log_level, message=log_message))


def claim_next_tranche(campaign_id: int, size: int) -> list[SendItem]:
    with db_session() as db:
        items = db.execute(
            select(SendItem).where(SendItem.campaign_id == campaign_id, SendItem.status == "pending")
            .order_by(SendItem.id).limit(size)
        ).scalars().all()
        for item in items:
            item.status = "processing"
        return list(items)


def update_item(item_id: int, status: str, *, error: str | None = None, attempts: int | None = None, sent: bool = False) -> None:
    with db_session() as db:
        item = db.get(SendItem, item_id)
        if item is None:
            return
        item.status = status
        if attempts is not None:
            item.attempts = attempts
        if error is not None:
            item.last_error = (error or "")[:2000] or None
        if sent:
            item.sent_at = datetime.now()


def count_items(campaign_id: int, status: str) -> int:
    with db_session() as db:
        return db.execute(
            select(func.count(SendItem.id)).where(SendItem.campaign_id == campaign_id, SendItem.status == status)
        ).scalar_one()


def finalize_campaign(campaign_id: int, cancelled: bool) -> None:
    with db_session() as db:
        db.execute(
            update(SendItem).where(SendItem.campaign_id == campaign_id, SendItem.status.in_(("pending", "processing")))
            .values(status="cancelled")
        )
        c = db.get(Campaign, campaign_id)
        if c is None:
            return
        c.status = "cancelled" if cancelled else "completed"
        c.completed_at = datetime.now()
        counts = status_counts(campaign_id)
        db.add(LogEntry(
            campaign_id=campaign_id,
            level="warning" if cancelled else "success",
            message=(f"Invio annullato: {counts['sent']} inviate, resto annullato" if cancelled else
                     f"Invio completato: {counts['sent']} inviate, {counts['failed_temp'] + counts['failed_perm']} fallite"),
        ))


def revert_processing(campaign_id: int) -> int:
    with db_session() as db:
        return db.execute(
            update(SendItem).where(SendItem.campaign_id == campaign_id, SendItem.status == "processing")
            .values(status="pending")
        ).rowcount


def recover_interrupted() -> None:
    """Al riavvio: gli item in elaborazione tornano in coda; gli invii riprendono da soli."""
    with db_session() as db:
        db.execute(update(SendItem).where(SendItem.status == "processing").values(status="pending"))


def campaign_items(campaign_id: int, status: str = "", page: int = 1, per_page: int = 50):
    with db_session() as db:
        stmt = select(SendItem).where(SendItem.campaign_id == campaign_id)
        if status:
            stmt = stmt.where(SendItem.status == status)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = db.execute(stmt.order_by(SendItem.id).offset((page - 1) * per_page).limit(per_page)).scalars().all()
        return [
            {
                "email": r.email, "first_name": r.first_name or "", "last_name": r.last_name or "",
                "status": r.status, "attempts": r.attempts, "last_error": r.last_error or "",
                "sent_at": r.sent_at.strftime("%d/%m/%Y %H:%M") if r.sent_at else "",
            }
            for r in rows
        ], total


def export_items_csv(campaign_id: int) -> str:
    items, _ = campaign_items(campaign_id, per_page=1_000_000)
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["email", "nome", "cognome", "stato", "tentativi", "ultimo_errore", "inviata_il"])
    for r in items:
        writer.writerow([r["email"], r["first_name"], r["last_name"], r["status"], r["attempts"], r["last_error"], r["sent_at"]])
    return buf.getvalue()


def add_log(campaign_id: int | None, level: str, message: str, detail: str | None = None) -> None:
    with db_session() as db:
        db.add(LogEntry(campaign_id=campaign_id, level=level, message=message, detail=detail))


def list_logs(campaign_id: int, after_id: int = 0, limit: int = 500) -> list[LogEntry]:
    with db_session() as db:
        stmt = (select(LogEntry).where(LogEntry.id > after_id, LogEntry.campaign_id == campaign_id)
                .order_by(LogEntry.id.desc()).limit(limit))
        return list(reversed(db.execute(stmt).scalars().all()))


def dashboard_stats() -> dict:
    with db_session() as db:
        return {
            "contacts": db.execute(select(func.count(Contact.id))).scalar_one(),
            "groups": db.execute(select(func.count(Group.id))).scalar_one(),
            "templates": db.execute(select(func.count(EmailTemplate.id))).scalar_one(),
            "smtp_active": db.execute(select(func.count(SmtpServer.id)).where(SmtpServer.active.is_(True))).scalar_one(),
            "campaigns_open": db.execute(
                select(func.count(Campaign.id)).where(Campaign.status.in_(("running", "scheduled", "paused")))
            ).scalar_one(),
        }
