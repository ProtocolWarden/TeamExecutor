# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 ProtocolWarden
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Provide stub modules for packages that aren't installed in the test environment
_rxp_stub = MagicMock()


class _RuntimeResult:
    """Minimal RuntimeResult stub for executor tests."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_rxp_stub.contracts.runtime_result.RuntimeResult = _RuntimeResult

sys.modules.setdefault("rxp", _rxp_stub)
sys.modules.setdefault("rxp.contracts", _rxp_stub.contracts)
sys.modules.setdefault("rxp.contracts.runtime_result", _rxp_stub.contracts.runtime_result)
sys.modules.setdefault("cxrp", MagicMock())
