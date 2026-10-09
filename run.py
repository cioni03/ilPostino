#!/usr/bin/env python3
"""Punto d'ingresso: avvia Newsletter Studio con `python run.py`.

Se lanciato con un interprete diverso da quello della venv locale (es. il
Python di sistema), riavvia automaticamente se stesso con `.venv/bin/python`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # niente __pycache__ per i moduli importati di seguito

BASE_DIR = Path(__file__).resolve().parent
VENV_PYTHON = BASE_DIR / ".venv" / "bin" / "python"


def _ensure_interpreter() -> None:
    # Usa prima la venv: la versione di sistema non è quella che eseguirà l'app.
    if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    # Versione minima richiesta dalla sintassi usata (PEP 604, pydantic, ecc.).
    if sys.version_info < (3, 12):
        print(
            f"Attenzione: Python {sys.version.split()[0]} non è supportato (serve 3.12+).\n"
            f"Interprete in uso: {sys.executable}",
            file=sys.stderr,
        )
    # Senza un interprete compatibile, mostra come creare l'ambiente.
    if sys.version_info < (3, 12):
        print(
            "\nCrea l'ambiente con Python 3.12+ e riprova:\n"
            "  uv python install 3.12 && uv venv .venv --python 3.12\n"
            "  uv pip install -r requirements.txt --python .venv/bin/python\n"
            "  python3.12 run.py   (oppure: .venv/bin/python run.py)",
            file=sys.stderr,
        )
        sys.exit(1)


_ensure_interpreter()

from app.main import main  # noqa: E402  (dopo i controlli sull'interprete)

if __name__ == "__main__":
    main()
