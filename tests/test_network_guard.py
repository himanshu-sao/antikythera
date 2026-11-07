"""Tests for the autouse ``network_guard`` fixture in the root conftest.

No test here connects anywhere: blocked hosts are refused before the real
connect runs, and the loopback / marked cases only inspect what is installed.
"""
import socket
import types

import pytest

import conftest as root_conftest


def _is_guarded():
    return getattr(socket.socket.connect, root_conftest._GUARD_FLAG, False)


def test_guard_is_installed_by_default():
    assert _is_guarded()


def test_blocked_connect_is_refused_and_recorded(network_guard):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OSError, match="network blocked"):
            s.connect(("203.0.113.7", 443))  # TEST-NET-3, never reached
    finally:
        s.close()
    assert network_guard == ["203.0.113.7"]
    # The guard would fail this test at teardown; clear to show it is the
    # recording (not the OSError) that drives that failure.
    network_guard.clear()


def test_hostname_is_blocked_before_any_dns(network_guard):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(OSError, match="network blocked"):
            s.connect(("example.com", 80))
    finally:
        s.close()
    assert network_guard == ["example.com"]
    network_guard.clear()


def test_swallowed_oserror_is_still_recorded(network_guard):
    """Code that catches the OSError must not hide the attempt."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("198.51.100.9", 80))
    except OSError:
        pass
    finally:
        s.close()
    assert network_guard == ["198.51.100.9"]
    network_guard.clear()


def test_multiple_attempts_all_recorded(network_guard):
    for host in ("203.0.113.1", "203.0.113.2"):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with pytest.raises(OSError):
                s.connect((host, 1))
        finally:
            s.close()
    assert network_guard == ["203.0.113.1", "203.0.113.2"]
    network_guard.clear()


def test_loopback_connect_is_delegated_to_real_connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        # Port 1 on loopback is refused locally; reaching ConnectionRefusedError
        # proves the guard delegated instead of raising its own OSError.
        with pytest.raises(OSError) as exc:
            s.connect(("127.0.0.1", 1))
        assert "network blocked" not in str(exc.value)
    finally:
        s.close()


@pytest.mark.parametrize(
    "address, allowed",
    [
        (("127.0.0.1", 80), True),
        (("localhost", 80), True),
        (("::1", 80, 0, 0), True),
        ("/tmp/some.sock", True),          # AF_UNIX path: not network traffic
        (("8.8.8.8", 53), False),
        (("example.com", 443), False),
        (("0.0.0.0", 80), False),
        (("2001:db8::1", 80, 0, 0), False),
    ],
)
def test_is_allowed_connect_matrix(address, allowed):
    assert root_conftest._is_allowed_connect(address) is allowed


@pytest.mark.parametrize("marker", ["network", "live_llm"])
def test_guard_applies_false_for_opt_out_markers(marker):
    node = types.SimpleNamespace(
        get_closest_marker=lambda name: object() if name == marker else None
    )
    assert root_conftest._guard_applies(node) is False


def test_guard_applies_true_without_markers():
    node = types.SimpleNamespace(get_closest_marker=lambda name: None)
    assert root_conftest._guard_applies(node) is True


def test_guard_applies_true_for_unrelated_marker():
    node = types.SimpleNamespace(
        get_closest_marker=lambda name: object() if name == "watcher" else None
    )
    assert root_conftest._guard_applies(node) is True


@pytest.mark.network
def test_network_marked_test_is_not_guarded(network_guard):
    """No connection is made: only the absence of the guard is asserted."""
    assert not _is_guarded()
    assert network_guard == []


@pytest.mark.live_llm
def test_live_llm_marked_test_is_not_guarded(network_guard):
    assert not _is_guarded()
    assert network_guard == []
