"""Invio email via aiosmtplib, classificazione errori e diagnostica connessione."""

from __future__ import annotations

import asyncio
import html as html_module
import re
import socket
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

import aiosmtplib
from aiosmtplib.errors import SMTPAuthenticationError, SMTPNotSupported

TIMEOUT = 20
_TAG_RE = re.compile(r"<[^>]+>")


class MailSendError(Exception):
    def __init__(self, kind: str, detail: str):  # kind: auth | perm | temp
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


def classify_smtp_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, SMTPAuthenticationError):
        return "auth", f"Credenziali rifiutate dal server: {exc}"
    from aiosmtplib.errors import (SMTPConnectError, SMTPDataError, SMTPHeloError, SMTPRecipientsRefused,
                                   SMTPResponseException, SMTPSenderRefused, SMTPServerDisconnected,
                                   SMTPConnectTimeoutError)
    if isinstance(exc, (SMTPRecipientsRefused, SMTPSenderRefused, SMTPNotSupported)):
        return "perm", f"Destinatario, mittente o funzione rifiutata: {exc}"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, SMTPConnectTimeoutError)):
        return "temp", "Timeout: il server non ha risposto in tempo"
    if isinstance(exc, (SMTPConnectError, SMTPServerDisconnected, ConnectionError, OSError)):
        return "temp", f"Problema di connessione: {exc}"
    if isinstance(exc, (SMTPResponseException, SMTPDataError, SMTPHeloError)):
        code = getattr(exc, "code", None)
        kind = "perm" if code is not None and code >= 500 else "temp"
        return kind, f"Errore del server ({code}): {exc}"
    import ssl
    if isinstance(exc, ssl.SSLError):
        return "perm", f"Errore TLS/certificato: {exc}"
    return "temp", f"Errore imprevisto: {type(exc).__name__}: {exc}"


def html_to_text(html: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", html or "")
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = html_module.unescape(_TAG_RE.sub("", text))
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def build_message(*, from_addr: str, from_name: str | None, reply_to: str | None, to_addr: str,
                  subject: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((from_name or "", from_addr))
    msg["To"] = to_addr
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_addr.split("@")[-1] if "@" in from_addr else "localhost")
    msg["X-Mailer"] = "Newsletter Studio (locale)"
    msg["Precedence"] = "bulk"
    msg.set_content(html_to_text(html) or " ")
    msg.add_alternative(html or "<html><body></body></html>", subtype="html")
    return msg


def _smtp_instance(smtp: dict) -> aiosmtplib.SMTP:
    return aiosmtplib.SMTP(hostname=smtp["host"], port=int(smtp.get("port") or 587),
                           use_tls=smtp.get("security") == "ssl", timeout=TIMEOUT)


async def _connect(smtp: dict, client: aiosmtplib.SMTP) -> None:
    await client.connect()
    if smtp.get("security") == "tls":
        await client.starttls()
    if smtp.get("username"):
        await client.login(smtp["username"], smtp.get("password") or "")


async def send_email(smtp: dict, *, to_addr: str, subject: str, html: str) -> None:
    """Invio singolo con connessione usa-e-getta (email di test)."""
    client = _smtp_instance(smtp)
    try:
        await _connect(smtp, client)
        await client.send_message(build_message(
            from_addr=smtp["sender_email"], from_name=smtp.get("sender_name"),
            reply_to=smtp.get("reply_to"), to_addr=to_addr, subject=subject, html=html,
        ))
    except Exception as e:
        raise MailSendError(*classify_smtp_error(e)) from e
    finally:
        try:
            await client.quit()
        except Exception:
            pass


class SmtpSession:
    """Connessione SMTP persistente per il worker, riconnessa automaticamente."""

    def __init__(self, smtp: dict):
        self._cfg = smtp
        self._client: aiosmtplib.SMTP | None = None

    def reset(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                asyncio.get_running_loop().create_task(_safe_quit(client))
            except RuntimeError:
                pass

    async def send(self, msg: EmailMessage) -> None:
        if self._client is None:
            self._client = _smtp_instance(self._cfg)
            await _connect(self._cfg, self._client)
        await self._client.send_message(msg)

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await _safe_quit(client)


async def _safe_quit(client: aiosmtplib.SMTP) -> None:
    try:
        await client.quit()
    except Exception:
        pass


# ---------------------------------------------------------------- diagnostica

@dataclass
class StepResult:
    name: str
    ok: bool
    ms: int
    detail: str
    hint: str = ""


@dataclass
class DiagnosisResult:
    ok: bool
    steps: list[StepResult]
    summary: str


_HINTS = {
    "dns": "Verifica il nome host: potrebbe essere errato o non raggiungibile dalla tua rete.",
    "tcp": "Verifica la porta e che il firewall/antivirus non blocchi la connessione in uscita.",
    "tls": "Il server potrebbe non supportare STARTTLS su questa porta: prova a cambiare sicurezza o porta (465/587/25).",
    "auth": "Utente o password errati. Se usi Gmail/Outlook serve una «password per app».",
    "noop": "La connessione si è chiusa subito dopo il login: possibili limiti del provider.",
}


async def diagnose_smtp(*, host: str, port: int, security: str, username: str | None,
                        password: str | None, sender_email: str) -> DiagnosisResult:
    steps: list[StepResult] = [StepResult("Mittente", bool(sender_email and "@" in sender_email), 0, sender_email or "—",
                                          "" if sender_email and "@" in sender_email else "L'indirizzo del mittente non è un'email valida.")]
    t0 = time.perf_counter()
    try:  # DNS
        loop = asyncio.get_running_loop()
        await asyncio.wait_for(loop.run_in_executor(None, socket.getaddrinfo, host, port), timeout=5)
        steps.append(StepResult("Risoluzione DNS", True, int((time.perf_counter() - t0) * 1000), f"Host {host} risolto"))
    except Exception as e:
        steps.append(StepResult("Risoluzione DNS", False, int((time.perf_counter() - t0) * 1000), str(e), _HINTS["dns"]))
        return DiagnosisResult(False, steps, "Impossibile risolvere il nome host.")

    client = _smtp_instance({"host": host, "port": port, "security": security, "username": username, "password": password})
    t0 = time.perf_counter()
    try:  # TCP (+ SSL implicito)
        await client.connect()
        steps.append(StepResult("Connessione TCP" + (" + SSL" if security == "ssl" else ""), True,
                                int((time.perf_counter() - t0) * 1000), f"Connesso a {host}:{port}"))
    except Exception as e:
        steps.append(StepResult("Connessione TCP", False, int((time.perf_counter() - t0) * 1000), str(e), _HINTS["tcp"]))
        return DiagnosisResult(False, steps, "Connessione al server non riuscita.")

    try:
        if security == "tls":  # STARTTLS
            t0 = time.perf_counter()
            try:
                await client.starttls()
                steps.append(StepResult("STARTTLS", True, int((time.perf_counter() - t0) * 1000), "Canale cifrato stabilito"))
            except Exception as e:
                steps.append(StepResult("STARTTLS", False, int((time.perf_counter() - t0) * 1000), str(e), _HINTS["tls"]))
                return DiagnosisResult(False, steps, "Negoziazione TLS non riuscita.")
        if username:  # AUTH
            t0 = time.perf_counter()
            try:
                await client.login(username, password or "")
                steps.append(StepResult("Autenticazione", True, int((time.perf_counter() - t0) * 1000), f"Login OK come {username}"))
            except Exception as e:
                steps.append(StepResult("Autenticazione", False, int((time.perf_counter() - t0) * 1000), str(e), _HINTS["auth"]))
                return DiagnosisResult(False, steps, "Credenziali rifiutate.")
        else:
            steps.append(StepResult("Autenticazione", True, 0, "Non richiesta"))
        try:  # NOOP
            t0 = time.perf_counter()
            await client.noop()
            steps.append(StepResult("Sessione (NOOP)", True, int((time.perf_counter() - t0) * 1000), "Il server risponde"))
        except Exception as e:
            steps.append(StepResult("Sessione (NOOP)", False, int((time.perf_counter() - t0) * 1000), str(e), _HINTS["noop"]))
        return DiagnosisResult(True, steps, "Connessione verificata: il server è pronto all'invio.")
    finally:
        await _safe_quit(client)
