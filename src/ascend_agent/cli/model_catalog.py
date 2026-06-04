"""Compatibility module for provider presets."""

from __future__ import annotations

import sys

from ascend_agent.providers import catalog as _provider_catalog

sys.modules[__name__] = _provider_catalog
