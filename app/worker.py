"""Worker background: campagne a tranche con annullamento e auto-pausa."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

from app import services, templating
from app.mailer import MailSendError, SmtpSession, build_message, classify_smtp_error

logger = logging.getLogger("newsletter.worker")


class CampaignTask:
    def __init__(self, campaign_id: int):
        self.campaign_id = campaign_id
        self.cancel = False
        self.task: asyncio.Task | None = None

    @property
    def alive(self) -> bool:
        return self.task is not None and not self.task.done()


class CampaignManager:
    def __init__(self) -> None:
        self.tasks: dict[int, CampaignTask] = {}

    def start(self, campaign_id: int) -> None:
        existing = self.tasks.get(campaign_id)
        if existing is not None and existing.alive:
            return
        ct = CampaignTask(campaign_id)
        ct.task = asyncio.create_task(self._guarded(ct))
        self.tasks[campaign_id] = ct

    def cancel(self, campaign_id: int) -> None:
        campaign = services.get_campaign(campaign_id)
        if campaign is None or campaign.status not in ("running", "paused", "scheduled"):
            return
        ct = self.tasks.get(campaign_id)
        if ct is not None and ct.alive:
            ct.cancel = True  # il loop finalizza da solo
        else:
            services.finalize_campaign(campaign_id, cancelled=True)

    def bootstrap(self) -> None:
        """Al riavvio: ripristina gli item e riprende automaticamente gli invii aperti."""
        services.recover_interrupted()
        for campaign in services.list_campaigns():
            if campaign.status in ("running", "scheduled"):
                self.start(campaign.id)
                logger.info("campagna %s ripresa automaticamente", campaign.id)

    async def _guarded(self, ct: CampaignTask) -> None:
        try:
            await self._run(ct)
        except Exception as e:  # il worker non deve mai morire in silenzio
            logger.exception("errore interno worker campagna %s", ct.campaign_id)
            services.set_campaign_status(ct.campaign_id, "paused", reason=f"Errore interno del worker: {e}",
                                         log_message=f"Errore interno: {e}", log_level="critical")
            services.revert_processing(ct.campaign_id)

    async def _sleep(self, ct: CampaignTask, seconds: float) -> None:
        end = time.monotonic() + max(0.0, seconds)
        while not ct.cancel and time.monotonic() < end:
            await asyncio.sleep(min(0.5, end - time.monotonic()))

    async def _run(self, ct: CampaignTask) -> None:
        campaign_id = ct.campaign_id
        # attesa dell'eventuale partenza programmata
        while True:
            campaign = services.get_campaign(campaign_id)
            if campaign is None or ct.cancel or campaign.status not in ("scheduled",):
                break
            if campaign.scheduled_at is None or (campaign.scheduled_at - datetime.now()).total_seconds() <= 0:
                services.set_campaign_status(campaign_id, "running", started=True, log_message="Partenza dell'invio programmato.")
                break
            await asyncio.sleep(1)

        campaign = services.get_campaign(campaign_id)
        if campaign is None or campaign.status == "cancelled":
            return
        if campaign.status != "running":
            services.set_campaign_status(campaign_id, "running", started=True)

        smtp = dict(campaign.smtp_snapshot or {})
        session = SmtpSession(smtp)
        threshold = services.DEFAULT_SEND["error_threshold"]
        rate_limit = smtp.get("rate_limit_emails_per_hour")
        rate_interval = (3600.0 / rate_limit) if rate_limit else 0.0
        max_retries, retry_delay = campaign.max_retries, campaign.retry_delay_seconds
        consecutive_errors = 0

        try:
            while not ct.cancel:
                items = services.claim_next_tranche(campaign_id, campaign.tranche_size)
                if not items:
                    break
                for item in items:
                    if ct.cancel:
                        break
                    context = templating.context_for({
                        "email": item.email, "first_name": item.first_name, "last_name": item.last_name,
                        "company": item.company, "tags": item.tags,
                    })
                    try:
                        subject = templating.render(campaign.subject, context)
                        html = templating.render(campaign.html_body, context)
                    except templating.TemplateError as e:
                        services.update_item(item.id, "failed_perm", error=f"errore template: {e}", attempts=1)
                        consecutive_errors += 1
                        continue

                    attempts = 0
                    while True:
                        try:
                            await session.send(build_message(
                                from_addr=smtp["sender_email"], from_name=smtp.get("sender_name"),
                                reply_to=smtp.get("reply_to"), to_addr=item.email, subject=subject, html=html,
                            ))
                            services.update_item(item.id, "sent", sent=True, attempts=attempts + 1)
                            consecutive_errors = 0
                            break
                        except Exception as e:
                            session.reset()
                            attempts += 1
                            kind, detail = classify_smtp_error(e)
                            if kind == "auth":
                                services.update_item(item.id, "failed_perm", error=detail, attempts=attempts)
                                await self._auto_pause(campaign_id, f"Credenziali SMTP rifiutate: {detail}")
                                return
                            if kind == "perm" or attempts > max_retries:
                                services.update_item(item.id, "failed_perm" if kind == "perm" else "failed_temp",
                                                     error=detail, attempts=attempts)
                                services.add_log(campaign_id, "error", f"{item.email}: {detail}")
                                consecutive_errors += 1
                                break
                            await self._sleep(ct, retry_delay)
                            if ct.cancel:
                                services.update_item(item.id, "pending", error=detail)
                                return
                    if consecutive_errors >= threshold:
                        await self._auto_pause(campaign_id, f"{consecutive_errors} errori consecutivi.")
                        return
                    if rate_interval:
                        await self._sleep(ct, rate_interval)

                if services.count_items(campaign_id, "pending") > 0 and not ct.cancel:
                    services.add_log(campaign_id, "info",
                                     f"Tranca completata. Pausa di {campaign.pause_seconds}s prima della prossima.")
                    await self._sleep(ct, campaign.pause_seconds)
        finally:
            await session.close()
            campaign = services.get_campaign(campaign_id)
            if campaign is not None and campaign.status in ("running", "scheduled"):
                services.finalize_campaign(campaign_id, cancelled=ct.cancel)
            elif campaign is not None and campaign.status == "paused":
                services.revert_processing(campaign_id)

    async def _auto_pause(self, campaign_id: int, reason: str) -> None:
        services.set_campaign_status(campaign_id, "paused", reason=reason,
                                     log_message=f"AUTO-PAUSA: {reason}", log_level="critical")


manager = CampaignManager()
