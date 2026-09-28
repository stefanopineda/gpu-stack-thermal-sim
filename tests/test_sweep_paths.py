from pathlib import Path

from gpusim.cli import choose_port
from gpusim.sweep import resolve_plots_dir


def test_default_out_keeps_plots_at_repo_plots_dir():
    assert resolve_plots_dir(Path("results"), None) == Path("plots")


def test_custom_out_puts_plots_under_that_tree():
    assert resolve_plots_dir(Path("/tmp/gpusim-out"), None) == Path("/tmp/gpusim-out/plots")


def test_explicit_plots_win():
    assert resolve_plots_dir(Path("/tmp/gpusim-out"), Path("/tmp/charts")) == Path("/tmp/charts")


def test_busy_port_moves_to_a_free_one():
    import socket

    held = socket.socket()
    held.bind(("127.0.0.1", 0))
    busy = held.getsockname()[1]
    try:
        chosen, moved = choose_port("127.0.0.1", busy)
        assert moved is True
        assert chosen != busy
    finally:
        held.close()
