"""
2.13 — scripts/run_orchestrator.py loop behaviour.

The loop is exercised through ``run_loop`` with fake pipeline / sleep /
stop-event objects, so no real sleeping and no real pipeline run happens.
"""
import importlib.util
import logging
import os
import signal
import threading

import pytest

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "run_orchestrator.py",
)


@pytest.fixture(scope="module")
def ro():
    spec = importlib.util.spec_from_file_location("run_orchestrator_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Recorder:
    """Fake sleep: records intervals and optionally sets the stop event after N calls."""

    def __init__(self, stop=None, stop_after=None):
        self.calls = []
        self._stop = stop
        self._stop_after = stop_after

    def __call__(self, seconds):
        self.calls.append(seconds)
        if self._stop is not None and self._stop_after is not None \
                and len(self.calls) >= self._stop_after:
            self._stop.set()


class TestRunLoopExceptions:
    def test_exception_is_logged_and_loop_continues(self, ro, caplog):
        stop = threading.Event()
        results = iter([RuntimeError("first cycle blew up"), 3, 2])
        calls = {"n": 0}

        def pipeline():
            calls["n"] += 1
            r = next(results)
            if isinstance(r, Exception):
                raise r
            return r

        sleep = _Recorder(stop=stop, stop_after=3)
        with caplog.at_level(logging.ERROR):
            ro.run_loop(pipeline, sleep, stop, interval=30)

        assert calls["n"] == 3                   # kept going after the exception
        assert sleep.calls == [30, 30, 30]       # normal sleep after the failed cycle too
        logged = [r.exc_info[1] for r in caplog.records if r.exc_info]
        assert any(isinstance(e, RuntimeError) and "first cycle blew up" in str(e)
                   for e in logged)

    def test_exception_does_not_escape_run_loop(self, ro):
        stop = threading.Event()

        def pipeline():
            stop.set()
            raise ValueError("boom")

        ro.run_loop(pipeline, _Recorder(), stop, interval=1)   # must not raise

    def test_consecutive_exceptions_keep_running(self, ro):
        stop = threading.Event()
        calls = {"n": 0}

        def pipeline():
            calls["n"] += 1
            if calls["n"] < 5:
                raise RuntimeError("still failing")
            return 0

        ro.run_loop(pipeline, _Recorder(stop=stop, stop_after=5), stop, interval=2)
        assert calls["n"] == 5

    def test_base_exception_like_keyboard_interrupt_is_not_swallowed(self, ro):
        stop = threading.Event()

        def pipeline():
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            ro.run_loop(pipeline, _Recorder(), stop, interval=1)


class TestRunLoopStop:
    def test_stop_set_before_start_runs_no_cycle(self, ro):
        stop = threading.Event()
        stop.set()
        calls = {"n": 0}

        def pipeline():
            calls["n"] += 1
            return 0

        cycles = ro.run_loop(pipeline, _Recorder(), stop, interval=1)
        assert calls["n"] == 0
        assert cycles == 0

    def test_stop_during_cycle_finishes_that_cycle_then_exits(self, ro):
        stop = threading.Event()
        calls = {"n": 0}

        def pipeline():
            calls["n"] += 1
            stop.set()                      # signal arrives mid-cycle
            return 4

        sleep = _Recorder()
        cycles = ro.run_loop(pipeline, sleep, stop, interval=30)
        assert calls["n"] == 1                # current cycle completed
        assert cycles == 1
        assert sleep.calls == []              # no further sleep once stop is set

    def test_stop_during_sleep_exits_without_another_cycle(self, ro):
        stop = threading.Event()
        calls = {"n": 0}

        def pipeline():
            calls["n"] += 1
            return 0

        sleep = _Recorder(stop=stop, stop_after=1)
        ro.run_loop(pipeline, sleep, stop, interval=30)
        assert calls["n"] == 1
        assert sleep.calls == [30]

    def test_loop_runs_until_stopped(self, ro):
        stop = threading.Event()
        calls = {"n": 0}

        def pipeline():
            calls["n"] += 1
            return 1

        cycles = ro.run_loop(pipeline, _Recorder(stop=stop, stop_after=4), stop, interval=5)
        assert calls["n"] == 4
        assert cycles == 4

    def test_returns_cycle_count_including_failed_cycles(self, ro):
        stop = threading.Event()
        seq = iter([1, RuntimeError("x"), 2])

        def pipeline():
            r = next(seq)
            if isinstance(r, Exception):
                raise r
            if r == 2:
                stop.set()
            return r

        cycles = ro.run_loop(pipeline, _Recorder(), stop, interval=1)
        assert cycles == 3


class TestSignalHandling:
    def test_install_signal_handlers_sets_stop_on_sigterm_and_sigint(self, ro):
        stop = threading.Event()
        previous = {
            signal.SIGTERM: signal.getsignal(signal.SIGTERM),
            signal.SIGINT: signal.getsignal(signal.SIGINT),
        }
        try:
            ro.install_signal_handlers(stop)
            handler_term = signal.getsignal(signal.SIGTERM)
            handler_int = signal.getsignal(signal.SIGINT)
            assert callable(handler_term) and callable(handler_int)
            assert not stop.is_set()
            handler_term(signal.SIGTERM, None)
            assert stop.is_set()
            stop.clear()
            handler_int(signal.SIGINT, None)
            assert stop.is_set()
        finally:
            for sig, h in previous.items():
                signal.signal(sig, h)

    def test_main_uses_loop_and_returns_zero(self, ro, monkeypatch):
        """main wires the real pieces; here everything is faked so nothing runs."""
        stop_holder = {}

        def fake_loop(pipeline, sleep, stop, interval=30):
            stop_holder["stop"] = stop
            pipeline()
            return 1

        monkeypatch.setattr(ro, "run_loop", fake_loop)
        monkeypatch.setattr(ro, "run_pipeline", lambda: 0)
        monkeypatch.setattr(ro, "install_signal_handlers", lambda stop: None)
        assert ro.main() == 0
        assert isinstance(stop_holder["stop"], threading.Event)
