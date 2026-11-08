# tests/conftest.py — B1 (P1-3) test-only escape for adapter_module validation.
#
# api.integration_hub.add_integration / update_integration validate that a
# native integration's adapter_module is one of the canonical api.adapters.*
# modules (P1-3: _execute_native imports whatever string is stored, so an
# arbitrary importable module would run with the hub's access). Production
# never sets ANTIKYTHERA_ALLOW_ANY_ADAPTER_MODULE, so the API stays strict.
#
# Many existing unit tests build hubs backed by fake adapter modules
# (t8_fake_native_adapter, "x", ...) or rely on the historical mock_module
# default for a native add without a module, so the suite opts in here once.
# Tests that verify the validation itself delete the variable (see
# TestAdapterModuleValidation in tests/test_integration_hub.py), and tests
# that want the escape per call pass allow_any_module=True explicitly.

import os

os.environ.setdefault("ANTIKYTHERA_ALLOW_ANY_ADAPTER_MODULE", "1")
