"""Allow `python -m pib._engine` for dev."""

from .app import run

if __name__ == "__main__":
    raise SystemExit(run())
