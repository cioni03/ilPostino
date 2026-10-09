"""Bootstrap: creazione tabelle, registrazione pagine e avvio del server web."""

from __future__ import annotations

import logging

from nicegui import app as nicegui_app
from nicegui import ui as nicegui_ui

from app.config import settings
from app.db import Base, engine


def create_app() -> None:
    from app import ui as _ui  # noqa: F401  (registra le pagine come effetto collaterale)

    @nicegui_app.on_startup
    async def _startup() -> None:
        from app.worker import manager

        manager.bootstrap()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    Base.metadata.create_all(engine)  # crea solo le tabelle mancanti, i dati esistenti non si toccano
    create_app()
    nicegui_ui.run(
        host=settings.host,
        port=settings.port,
        title="ilPostino",
        reload=False,
        show=settings.show_browser,
        favicon="📬",
    )
