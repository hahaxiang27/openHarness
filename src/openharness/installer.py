#!/usr/bin/env python3
"""openHarness installation and configuration bootstrap module.

Supports OpenCode, Claude Code, and Codex backends.
"""

import json
import os
import sys
import shutil
import subprocess
from pathlib import Path

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from backend import SUPPORTED_BACKENDS, get_backend, resolve_backend_name, OpenCodeBackend


def get_openharness_agents_dir() -> Path:
    """Return the source agent directory bundled with openharness."""
    return Path(__file__).parent / "agents"


def get_openharness_config_template() -> dict:
    """Return the OpenCode configuration template."""
    openharness_permission = {
        "external_directory": {
            "~/.openharness/*": "allow"
        }
    }
    
    return {
        "agent": {
            "openharness-orchestrator": {
                "prompt": "{file:~/.config/opencode/agents/openharness-orchestrator.md}",
                "mode": "primary",
                "permission": openharness_permission
            },
            "openharness-initializer": {
                "prompt": "{file:~/.config/opencode/agents/openharness-initializer.md}",
                "mode": "primary",
                "permission": openharness_permission
            },
            "openharness-coder": {
                "prompt": "{file:~/.config/opencode/agents/openharness-coder.md}",
                "mode": "primary",
                "permission": openharness_permission
            },
            "openharness-tester": {
                "prompt": "{file:~/.config/opencode/agents/openharness-tester.md}",
                "mode": "primary",
                "permission": openharness_permission
            },
            "openharness-fixer": {
                "prompt": "{file:~/.config/opencode/agents/openharness-fixer.md}",
                "mode": "primary",
                "permission": openharness_permission
            },
            "openharness-reviewer": {
                "prompt": "{file:~/.config/opencode/agents/openharness-reviewer.md}",
                "mode": "primary",
                "permission": openharness_permission
            }
        },
        "mcp": {
            "playwright": {
                "type": "local",
                "command": ["npx", "@playwright/mcp@latest"],
                "enabled": True
            }
        }
    }


def is_initialized(backend=None) -> bool:
    """Check whether openHarness agent files are installed for the backend."""
    if backend is None:
        backend = get_backend()
    return backend.is_agents_initialized()


def initialize(backend=None) -> bool:
    """Install agent files and configuration for the selected backend."""
    if backend is None:
        backend = get_backend()

    if is_initialized(backend):
        return True
    
    try:
        src_dir = get_openharness_agents_dir()
        copied_files = backend.install_agents(src_dir)

        # OpenCode requires an additional JSON config merge.
        if isinstance(backend, OpenCodeBackend):
            openharness_config = get_openharness_config_template()
            backend.merge_config(openharness_config)

        print(f"[openHarness] Initialized {backend.name} config with {len(copied_files)} agents")
        return True
    except Exception as e:
        print(f"[openHarness] Failed to initialize: {e}")
        return False


def get_openharness_gitignore_content() -> str:
    """Return the recommended openHarness entries for `.gitignore`."""
    return """# openHarness runtime data
.openharness/
dev-log.txt
cycle-log.txt

# openHarness launcher scripts (should be installed globally via pip)
openharness
openharness.bat

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/

# System files
.DS_Store
Thumbs.db
"""


def update_gitignore(project_dir: str) -> None:
    """Update the project's `.gitignore` with openHarness rules."""
    gitignore_path = os.path.join(project_dir, ".gitignore")
    
    openharness_rules = [
        "# openHarness runtime data",
        ".openharness/",
        "dev-log.txt",
        "cycle-log.txt",
        "",
        "# openHarness launcher scripts (should be installed globally via pip)",
        "openharness",
        "openharness.bat",
    ]
    
    existing_content = ""
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except Exception:
            pass
    
    lines_to_add = []
    for rule in openharness_rules:
        if rule and rule not in existing_content:
            lines_to_add.append(rule)
    
    if lines_to_add:
        with open(gitignore_path, "a", encoding="utf-8") as f:
            if existing_content and not existing_content.endswith("\n"):
                f.write("\n")
            f.write("\n".join(lines_to_add) + "\n")
        print(f"[openHarness] Updated .gitignore with {len(lines_to_add)} rules")
    else:
        print("[openHarness] .gitignore already contains openHarness rules")


def init_git_repo():
    """Initialize a Git repository in the current project if needed."""
    project_dir = os.getcwd()
    
    # 1. Check subdirectories for `.git` first.
    for entry in os.listdir(project_dir):
        entry_path = os.path.join(project_dir, entry)
        if os.path.isdir(entry_path):
            sub_git_dir = os.path.join(entry_path, ".git")
            if os.path.exists(sub_git_dir):
                print(f"[openHarness] Git repo found in subdirectory: {entry}, skipping root init")
                return False
    
    # 2. Check whether the current directory is already inside a Git repository.
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10
        )
        if result.returncode == 0:
            print("[openHarness] Git repository already exists")
            update_gitignore(project_dir)
            return False
    except Exception:
        pass
    
    # 3. Check for `.git` in the current directory.
    git_dir = os.path.join(project_dir, ".git")
    if os.path.exists(git_dir):
        update_gitignore(project_dir)
        return False
    
    # 4. Only initialize when none of the checks found a repository.
    try:
        subprocess.run(["git", "init"], cwd=project_dir, check=True,
                       capture_output=True, encoding='utf-8', errors='replace')
        print("[openHarness] Initialized git repository")
        
        # 5. Create or update `.gitignore`.
        gitignore_path = os.path.join(project_dir, ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(get_openharness_gitignore_content())
            print("[openHarness] Created .gitignore with openHarness rules")
        else:
            update_gitignore(project_dir)
        
        return True
    except Exception as e:
        print(f"[openHarness] Failed to init git: {e}")
        return False


def check_and_install_dependencies():
    """Check for missing dependencies and install them if needed."""
    missing_deps = []
    
    # Check PyYAML.
    try:
        import yaml
    except ImportError:
        missing_deps.append("pyyaml")
    
    if missing_deps:
        print(f"[openHarness] Installing missing dependencies: {', '.join(missing_deps)}")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install"] + missing_deps,
                check=True,
                capture_output=True,
                encoding='utf-8',
                errors='replace'
            )
            print(f"[openHarness] Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"[openHarness] Failed to install dependencies: {e}")
            print(f"[openHarness] Please install manually: pip install {' '.join(missing_deps)}")


def ensure_input_directories(project_dir: str = "") -> None:
    """Ensure input/ directory structure exists, create or complete missing parts."""
    if not project_dir:
        project_dir = os.getcwd()
    required_dirs = [
        os.path.join(project_dir, "input", "prd"),
        os.path.join(project_dir, "input", "techspec"),
        os.path.join(project_dir, "input", "changes"),
    ]
    
    created = []
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            created.append(os.path.relpath(dir_path, project_dir))
    
    if created:
        print(f"[openHarness] Created input directories: {', '.join(created)}")
    else:
        print("[openHarness] Input directory structure already complete")


def check_and_initialize(backend_name=None) -> None:
    """Check and initialize the openHarness environment.

    Args:
        backend_name: Explicit backend name from `SUPPORTED_BACKENDS`.
            If omitted, load it from config or auto-detect it.
    """
    check_and_install_dependencies()
    
    backend = get_backend(resolve_backend_name(backend_name, os.getcwd()))
    
    if not is_initialized(backend):
        print(f"[openHarness] First run detected, initializing for {backend.name}...")
        initialize(backend)
    
    ensure_input_directories()
    
    # Validate backend CLI availability before starting.
    if not backend.is_installed():
        print("")
        print("=" * 60)
        print(f"  [WARNING] {backend.name} command not found!")
        print("")
        print(f"  openHarness requires {backend.name} to run. Please install it:")
        print(backend.get_install_hint())
        print("=" * 60)
        print("")


def uninstall() -> None:
    """Uninstall openHarness and clean local and optional global data."""
    print("[openHarness] Uninstalling...")
    
    # Read the current backend from config.yaml.
    project_dir = os.getcwd()
    backend = get_backend(resolve_backend_name(project_dir=project_dir))
    
    # 1. Remove agent files and config for the current backend.
    removed = backend.uninstall_agents()
    if removed:
        print(f"[openHarness] Removed from {backend.name}: {', '.join(removed)}")
    
    # 2. Also clean the other backends if they have installed openHarness agents.
    for other_name in SUPPORTED_BACKENDS:
        if other_name == backend.name:
            continue
        other_backend = get_backend(other_name)
        if other_backend.is_agents_initialized():
            other_removed = other_backend.uninstall_agents()
            if other_removed:
                print(f"[openHarness] Also removed from {other_name}: {', '.join(other_removed)}")
    
    # 3. Remove the current project's `.openharness/` directory and `dev-log.txt`.
    openharness_local = os.path.join(project_dir, ".openharness")
    dev_log = os.path.join(project_dir, "dev-log.txt")
    
    if os.path.exists(openharness_local):
        shutil.rmtree(openharness_local)
        print(f"[openHarness] Removed {openharness_local}")
    
    if os.path.exists(dev_log):
        os.remove(dev_log)
        print(f"[openHarness] Removed {dev_log}")
    
    # 4. Ask whether to delete global data under `~/.openharness/`.
    global_openharness = Path.home() / ".openharness"
    if global_openharness.exists():
        print(f"")
        print(f"[openHarness] Global data directory: {global_openharness}")
        print(f"        This contains learning data and metrics for ALL projects.")
        answer = input("        Delete global data? (y/N): ").strip().lower()
        if answer == "y":
            shutil.rmtree(global_openharness)
            print(f"[openHarness] Removed {global_openharness}")
        else:
            print(f"[openHarness] Kept {global_openharness}")
    
    print("")
    print("[openHarness] Uninstall complete.")
    
    # 5. Ask whether to uninstall the Python package as well.
    print("")
    print("[openHarness] Do you also want to remove the `hc` CLI package?")
    answer_pkg = input("        Uninstall openharness package? (Y/n): ").strip().lower()
    if answer_pkg != "n":
        print("[openHarness] Uninstalling openharness package...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "openharness", "-y"],
                check=True,
                encoding='utf-8',
                errors='replace'
            )
            print("[openHarness] openharness package removed.")
            print("[openHarness] All clean! openHarness has been completely removed.")
        except Exception as e:
            print(f"[openHarness] Failed to uninstall package: {e}")
            print("[openHarness] Please run manually:")
            print(f"        {sys.executable} -m pip uninstall openharness")
    else:
        print("[openHarness] Package kept. `hc` command is still available.")
        print("[openHarness] To remove later: python -m pip uninstall openharness")
