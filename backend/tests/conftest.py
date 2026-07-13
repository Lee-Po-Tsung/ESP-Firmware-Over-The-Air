"""Shared test setup.

`infrastructure.db` creates its engine at import time from `get_settings()`,
which defaults to `backend/data/`. Point `DATA_DIR` at a throwaway directory
before any test module can trigger that import, so running the suite never
touches real application data.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="ota-test-data-"))
