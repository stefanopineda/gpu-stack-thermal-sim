"""Command-line entry point. Subcommands are filled in by later modules."""

from __future__ import annotations

import typer

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Air-cooled multi-GPU airflow and temperature simulator (not CFD).",
)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
