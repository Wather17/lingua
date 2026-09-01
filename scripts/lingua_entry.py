"""Entrypoint usado exclusivamente pelo PyInstaller."""

from lingua.cli import app


if __name__ == "__main__":
    app(prog_name="lingua")
