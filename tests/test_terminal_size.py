import io
import struct

import pytest

from httpie_rich_terminal import terminal
from httpie_rich_terminal.terminal import TerminalSize, probe_size


def test_has_pixel_info_true_when_both_cell_dims_known():
    assert TerminalSize(80, 24, 8.0, 17.0).has_pixel_info is True


def test_has_pixel_info_false_when_cell_dims_are_zero():
    assert TerminalSize(80, 24, 0.0, 0.0).has_pixel_info is False
    assert TerminalSize(80, 24, 8.0, 0.0).has_pixel_info is False


def test_probe_size_computes_cell_dimensions(monkeypatch):
    # rows=24 cols=80 xpixel=640 ypixel=408 -> cells are 8.0 x 17.0
    packed = struct.pack("HHHH", 24, 80, 640, 408)
    monkeypatch.setattr(terminal.fcntl, "ioctl", lambda *a, **kw: packed)

    size = probe_size(fd=1)

    assert size.columns == 80
    assert size.rows == 24
    assert size.cell_width == pytest.approx(8.0)
    assert size.cell_height == pytest.approx(17.0)
    assert size.has_pixel_info is True


def test_probe_size_degrades_when_pixel_fields_are_zero(monkeypatch):
    packed = struct.pack("HHHH", 24, 80, 0, 0)
    monkeypatch.setattr(terminal.fcntl, "ioctl", lambda *a, **kw: packed)

    size = probe_size(fd=1)

    assert size.columns == 80
    assert size.rows == 24
    assert size.has_pixel_info is False


def test_probe_size_degrades_when_ioctl_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError(25, "Inappropriate ioctl for device")

    monkeypatch.setattr(terminal.fcntl, "ioctl", boom)

    size = probe_size(fd=1)

    assert size.has_pixel_info is False
    assert size.columns > 0
    assert size.rows > 0


def test_probe_size_degrades_when_columns_are_zero(monkeypatch):
    # A zero column count would make max-width maths collapse; treat as unknown.
    packed = struct.pack("HHHH", 0, 0, 0, 0)
    monkeypatch.setattr(terminal.fcntl, "ioctl", lambda *a, **kw: packed)

    size = probe_size(fd=1)

    assert size.columns > 0
    assert size.rows > 0
    assert size.has_pixel_info is False


def test_probe_size_degrades_without_ioctl_support(monkeypatch):
    # Windows has no fcntl/termios; the module still imports and probe_size
    # must return a usable default rather than raising NameError.
    #
    # The names must be deleted too, not just the flag flipped. With them
    # still bound, removing the guard leaves this test green: fd=1 is not a
    # tty under pytest, so fcntl.ioctl raises OSError, which the existing
    # except clause swallows into the very same _UNKNOWN_SIZE this asserts.
    # Deleting them makes a missing guard surface as NameError, which is not
    # in the except clause and therefore fails the test.
    monkeypatch.setattr(terminal, "_HAS_IOCTL", False)
    monkeypatch.delattr(terminal, "fcntl", raising=False)
    monkeypatch.delattr(terminal, "termios", raising=False)

    size = probe_size(fd=1)

    assert size.has_pixel_info is False
    assert size.columns > 0
    assert size.rows > 0


def test_probe_size_degrades_when_stdout_is_none(monkeypatch):
    # pythonw and detached daemons leave sys.__stdout__ as None.
    monkeypatch.setattr(terminal.sys, "__stdout__", None)

    size = probe_size()

    assert size.has_pixel_info is False
    assert size.columns > 0


def test_probe_size_degrades_when_stdout_has_no_fileno(monkeypatch):
    # pytest's capsys and various wrappers replace stdout with a StringIO,
    # whose fileno() raises io.UnsupportedOperation.
    monkeypatch.setattr(terminal.sys, "__stdout__", io.StringIO())

    size = probe_size()

    assert size.has_pixel_info is False
    assert size.columns > 0
