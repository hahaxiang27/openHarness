"""openHarness - AI-assisted human-in-the-loop development framework.

Supports OpenCode, Claude Code, and Codex backends.
"""

__version__ = "4.1.0"
__author__ = "openHarness"

import os
from pathlib import Path

def get_package_dir():
    """Return the package directory path."""
    return Path(__file__).parent

def get_agents_dir():
    """Return the agents directory path."""
    return get_package_dir() / "agents"

def get_opencode_config_template():
    """Return the OpenCode config template path."""
    return get_package_dir() / "opencode.json"
