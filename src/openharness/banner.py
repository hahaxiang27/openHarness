"""Terminal splash banners for openHarness CLI (e.g. after `oph init`)."""

from __future__ import annotations

import sys

# figlet -f standard openharness (ASCII, embedded to avoid runtime dependency)
_OPENHARNESS_ASCII = (
    "                        _                                    ",
    "  ___  _ __   ___ _ __ | |__   __ _ _ __ _ __   ___  ___ ___ ",
    " / _ \\| '_ \\ / _ \\ '_ \\| '_ \\ / _` | '__| '_ \\ / _ \\/ __/ __|",
    "| (_) | |_) |  __/ | | | | | | (_| | |  | | | |  __/\\__ \\__ \\",
    " \\___/| .__/ \\___|_| |_|_| |_|\\__,_|_|  |_| |_|\\___||___/___/",
    "      |_|                                                    ",
)


def print_init_completion_banner(backend_name: str) -> None:
    """Print a banner after successful project initialization."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    mount_hint = {
        "opencode": "当前坐骑 · OpenCode 轻鞍",
        "claude": "当前坐骑 · Claude 绒鞍",
        "codex": "当前坐骑 · Codex 铁鞍",
    }.get(backend_name.lower(), f"当前坐骑 · {backend_name}")

    print()
    for line in _OPENHARNESS_ASCII:
        print(line.rstrip())
    print()
    print("                        请选择你的坐骑")
    print()
    print("       +---------+  +---------+  +---------+  +---------+")
    print("      / ~~~~~~~ \\ / @@@@@@@ \\ / ####### \\ / ******* \\")
    print("     |  _|_|_  |  |  _|_|_  |  |  _|_|_  |  |  _|_|_  |")
    print("      \\_______/  \\_______/  \\_______/  \\_______/")
    print("      OpenCode      Claude       Codex      自由探索")
    print("       轻鞍           绒鞍           铁鞍           云鞍")
    print()
    print(f"      {mount_hint}")
    print()
