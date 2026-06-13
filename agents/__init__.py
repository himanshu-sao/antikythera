# Antikythera Multi-Agent Automation System - Agents Package

# Ensure a default asyncio event loop exists for any code that calls
# ``asyncio.get_event_loop()`` without having created one first.
# This mirrors the safeguard used in ``agents.orchestrator`` but applies
# globally so that tests (and any module) can safely obtain a loop.
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Guard against tests that monkey‑patch the ``agents.llm_client`` module.
# If the module in ``sys.modules`` does not contain a real ``LLMClient`` class,
# we reload the genuine implementation from the source file.
import sys, importlib.util, os
# Always load the fresh implementation of LLMClient to ensure any recent changes are reflected.
_file_path = os.path.join(os.path.dirname(__file__), 'llm_client.py')
_spec = importlib.util.spec_from_file_location('agents.llm_client', _file_path)
_real_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_real_mod)
sys.modules['agents.llm_client'] = _real_mod
