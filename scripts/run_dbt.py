#!/usr/bin/env python3
"""Ejecuta dbt con el perfil del proyecto y variables de .env."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "dbt" / "red_metropolitana"


def main() -> int:
    load_dotenv(ROOT / ".env")
    dbt = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    if not dbt.exists():
        raise RuntimeError("Instale requirements.txt en el entorno virtual antes de ejecutar dbt")
    return subprocess.call(
        [str(dbt), *sys.argv[1:], "--project-dir", str(PROJECT), "--profiles-dir", str(PROJECT)],
        cwd=ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
