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


# ----------------------------------------------------------------------
# P1-9: the guard also covers connect_ex, UDP sendto, DNS lookups and asyncio
# sock_connect. Every case below targets a documentation-range address or a
# host name and never reaches the network (the guard refuses first).
# ----------------------------------------------------------------------
def test_new_guards_are_installed_by_default():
    assert getattr(socket.socket.connect_ex, root_conftest._GUARD_FLAG, False)
    assert getattr(socket.socket.sendto, root_conftest._GUARD_FLAG, False)
    assert getattr(socket.getaddrinfo, root_conftest._GUARD_FLAG, False)


def test_connect_ex_to_remote_is_refused_and_recorded(network_guard):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = s.connect_ex(("203.0.113.9", 443))  # TEST-NET-3, never reached
    finally:
        s.close()
    assert result != 0  # reported as a failure, not a success
    assert network_guard == ["203.0.113.9"]
    network_guard.clear()


def test_connect_ex_to_hostname_is_recorded(network_guard):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        assert s.connect_ex(("remote.example.invalid", 80)) != 0
    finally:
        s.close()
    assert network_guard == ["remote.example.invalid"]
    network_guard.clear()


def test_connect_ex_to_loopback_is_delegated():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        # Port 1 on loopback is refused locally; the real connect_ex answers.
        assert s.connect_ex(("127.0.0.1", 1)) != 0
    finally:
        s.close()


def test_sendto_remote_udp_is_refused_and_recorded(network_guard):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(OSError, match="network blocked"):
            s.sendto(b"ping", ("203.0.113.9", 53))
    finally:
        s.close()
    assert network_guard == ["203.0.113.9"]
    network_guard.clear()


def test_sendto_with_flags_argument_is_checked(network_guard):
    """sendto(data, flags, address) must read the address from the last argument."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        with pytest.raises(OSError, match="network blocked"):
            s.sendto(b"ping", 0, ("203.0.113.10", 53))
    finally:
        s.close()
    assert network_guard == ["203.0.113.10"]
    network_guard.clear()


def test_sendto_loopback_is_delegated():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP to loopback needs no listener; the real sendto returns the byte count.
        assert s.sendto(b"x", ("127.0.0.1", 9)) == 1
    finally:
        s.close()


def test_getaddrinfo_remote_name_is_refused_and_recorded(network_guard):
    with pytest.raises(OSError, match="network blocked"):
        socket.getaddrinfo("remote.example.invalid", 443)
    assert network_guard == ["remote.example.invalid"]
    network_guard.clear()


def test_getaddrinfo_remote_address_literal_is_refused(network_guard):
    with pytest.raises(OSError, match="network blocked"):
        socket.getaddrinfo("203.0.113.9", 443)
    assert network_guard == ["203.0.113.9"]
    network_guard.clear()


def test_getaddrinfo_localhost_is_allowed_by_name():
    """localhost is matched by name and never resolved by the guard."""
    infos = socket.getaddrinfo("localhost", 80, type=socket.SOCK_STREAM)
    assert infos  # resolves through the real resolver, to loopback addresses


def test_getaddrinfo_loopback_literal_is_allowed():
    infos = socket.getaddrinfo("127.0.0.1", 80, type=socket.SOCK_STREAM)
    assert infos[0][4][0] == "127.0.0.1"


def test_getaddrinfo_none_host_is_allowed():
    """A None host (wildcard lookup used by bind helpers) is not a network lookup."""
    assert root_conftest._is_allowed_lookup(None) is True


def test_sock_connect_remote_is_refused_and_recorded(network_guard):
    import asyncio

    loop = asyncio.new_event_loop()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setblocking(False)
    try:
        with pytest.raises(OSError, match="network blocked"):
            loop.run_until_complete(loop.sock_connect(s, ("203.0.113.9", 443)))
    finally:
        s.close()
        loop.close()
    assert network_guard == ["203.0.113.9"]
    network_guard.clear()


@pytest.mark.parametrize(
    "host, allowed",
    [
        ("localhost", True),
        ("LOCALHOST", True),
        ("127.0.0.1", True),
        ("127.5.5.5", True),
        ("::1", True),
        ("::ffff:127.0.0.1", True),
        ("203.0.113.9", False),
        ("0.0.0.0", False),
        ("remote.example.invalid", False),
        ("localhost.example.invalid", False),
        (b"localhost", True),
    ],
)
def test_is_loopback_host_matrix(host, allowed):
    assert root_conftest._is_loopback_host(host) is allowed
