"""Configurazione letta dal file .env (creato da .env.example al primo avvio)."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

DEFAULTS = {
    "HOST": "127.0.0.1",
    "PORT": "8090",
    "DATABASE_PATH": "data/ilpostino.db",
    "SHOW_BROWSER": "true",
}


def _read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        example = BASE_DIR / ".env.example"
        ENV_FILE.write_text(example.read_text(encoding="utf-8") if example.exists() else "", encoding="utf-8")
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip().upper()] = value.strip()
    return values


class Settings:
    def __init__(self) -> None:
        values = {**DEFAULTS, **_read_env()}
        self.host = values["HOST"]
        self.port = int(values["PORT"])
        self.show_browser = values["SHOW_BROWSER"].lower() in ("1", "true", "yes")
        path = Path(values["DATABASE_PATH"])
        self.database_path_abs = path if path.is_absolute() else BASE_DIR / path


settings = Settings()
