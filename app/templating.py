"""Engine template Jinja2: variabili dei contatti e validazione."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateSyntaxError
from jinja2.meta import find_undeclared_variables

KNOWN_VARIABLES: dict[str, str] = {
    "first_name": "Nome",
    "last_name": "Cognome",
    "email": "Email",
    "company": "Azienda",
    "tags": "Tag (separati da virgola)",
}

SAMPLE_CONTEXT: dict[str, Any] = {
    "first_name": "Luca", "last_name": "Rossi", "email": "luca.rossi@example.com",
    "company": "Acme Srl", "tags": "clienti, vip",
}


class TemplateError(Exception):
    """Errore di sintassi o rendering del template."""


_env = Environment(autoescape=True, undefined=StrictUndefined)


def _compile(template_str: str):
    try:
        return _env.from_string(template_str or "")
    except TemplateSyntaxError as e:
        raise TemplateError(f"errore di sintassi Jinja2 alla riga {e.lineno}: {e.message}") from e


def render(template_str: str, context: dict[str, Any]) -> str:
    try:
        return _compile(template_str).render(**context)
    except TemplateError:
        raise
    except Exception as e:  # UndefinedError, ecc.
        raise TemplateError(str(e)) from e


def check_syntax(template_str: str) -> str | None:
    try:
        _compile(template_str)
        return None
    except TemplateError as e:
        return str(e)


def unknown_variables(template_str: str) -> list[str]:
    """Variabili usate che non fanno parte di quelle note."""
    try:
        source = _env.parse(template_str or "")
    except TemplateSyntaxError as e:
        raise TemplateError(f"errore di sintassi Jinja2 alla riga {e.lineno}: {e.message}") from e
    return sorted(find_undeclared_variables(source) - set(KNOWN_VARIABLES))


def context_for(recipient: dict[str, Any]) -> dict[str, Any]:
    return {
        "first_name": recipient.get("first_name") or "",
        "last_name": recipient.get("last_name") or "",
        "email": recipient.get("email") or "",
        "company": recipient.get("company") or "",
        "tags": recipient.get("tags") or "",
    }
