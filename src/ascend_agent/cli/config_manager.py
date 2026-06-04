"""Compatibility module for provider configuration."""

from __future__ import annotations

import sys

from ascend_agent.providers import config_manager as _provider_config_manager

sys.modules[__name__] = _provider_config_manager
