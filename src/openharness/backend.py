#!/usr/bin/env python3
"""openHarness AI backend abstraction layer.

Supports OpenCode, Claude Code, and Codex execution backends.
"""

import json
import os
import sys
import shutil
from pathlib import Path


# Claude Code agent frontmatter definitions.
CLAUDE_AGENT_FRONTMATTER = {
    "orchestrator": {
        "name": "openharness-orchestrator",
        "description": "Decision-maker agent that reads project state and decides next agent. Use when orchestrating the openHarness development loop.",
    },
    "initializer": {
        "name": "openharness-initializer",
        "description": "One-time project setup agent that scans PRD docs and generates feature list. Use for openHarness project initialization.",
    },
    "coder": {
        "name": "openharness-coder",
        "description": "Code implementation agent that picks pending features and implements them. Use for openHarness coding tasks.",
    },
    "tester": {
        "name": "openharness-tester",
        "description": "Multi-layer testing agent (static analysis, unit test, compilation). Use for openHarness testing tasks.",
    },
    "fixer": {
        "name": "openharness-fixer",
        "description": "Bug and violation fixing agent that reads test/review reports. Use for openHarness fix tasks.",
    },
    "reviewer": {
        "name": "openharness-reviewer",
        "description": "Code review and compliance checking agent. Use for openHarness code review tasks.",
    },
}


OPENHARNESS_AGENT_NAMES = ["orchestrator", "initializer", "coder", "tester", "fixer", "reviewer"]
SUPPORTED_BACKENDS = ("opencode", "claude", "codex")
DEFAULT_BACKEND = "opencode"


def _get_openharness_prompt_path(agent_name: str) -> str:
    return f"{{file:~/.config/opencode/agents/openharness-{agent_name}.md}}"


def _migrate_legacy_openharness_agent_config(user_config: dict):
    """Migrate only openharness-owned legacy OpenCode agent aliases.

    This removes duplicate registration without touching user-defined unprefixed
    agents that do not point at openHarness-managed prompt files.
    """
    agents = user_config.get("agent")
    if not isinstance(agents, dict):
        return

    for agent_name in OPENHARNESS_AGENT_NAMES:
        legacy_key = agent_name
        prefixed_key = f"openharness-{agent_name}"
        legacy_value = agents.get(legacy_key)

        if not isinstance(legacy_value, dict):
            continue

        if legacy_value.get("prompt") != _get_openharness_prompt_path(agent_name):
            continue

        if prefixed_key not in agents:
            agents[prefixed_key] = legacy_value

        del agents[legacy_key]


class Backend:
    """Abstract base class for AI execution backends."""

    name = ""

    def get_command_path(self):
        """Return the CLI command path."""
        raise NotImplementedError

    def build_run_cmd(self, agent, prompt, model=None):
        """Build the command list used to run an agent."""
        raise NotImplementedError

    def get_config_dir(self):
        """Return the backend config directory path."""
        raise NotImplementedError

    def get_agents_dir(self):
        """Return the directory where agent files are installed."""
        raise NotImplementedError

    def install_agents(self, src_dir):
        """Install agent files and return the installed filenames."""
        raise NotImplementedError

    def merge_config(self, openharness_config):
        """Merge or write backend configuration when needed."""
        raise NotImplementedError

    def uninstall_agents(self):
        """Remove installed agent files and clean backend configuration."""
        raise NotImplementedError

    def is_installed(self):
        """Return whether the backend CLI is available."""
        raise NotImplementedError

    def is_agents_initialized(self):
        """Return whether agent files are already installed."""
        agents_dir = self.get_agents_dir()
        marker = agents_dir / "openharness-orchestrator.md"
        return marker.exists()

    def get_available_models(self):
        """Return the list of available models."""
        return []

    def get_install_hint(self):
        """Return backend-specific installation guidance."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# OpenCode Backend
# ---------------------------------------------------------------------------

class OpenCodeBackend(Backend):
    """OpenCode (`opencode.ai`) execution backend."""

    name = "opencode"

    def get_command_path(self):
        # 1. Environment variable override.
        if os.environ.get("OPENCODE_PATH"):
            return os.environ["OPENCODE_PATH"]

        # 2. Search on PATH.
        found = shutil.which("opencode")
        if found:
            return found

        # 3. Check common install locations per platform.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Roaming" / "npm" / "opencode.cmd",
                home / "AppData" / "Local" / "npm-global" / "opencode.cmd",
                home / ".local" / "bin" / "opencode.exe",
                Path("C:/Program Files/nodejs/opencode.cmd"),
            ]
        else:
            candidates = [
                home / ".npm-global" / "bin" / "opencode",
                Path("/usr/local/bin/opencode"),
                Path("/opt/homebrew/bin/opencode"),
                home / ".local" / "bin" / "opencode",
                home / ".nvm" / "current" / "bin" / "opencode",
                home / ".volta" / "bin" / "opencode",
                home / ".bun" / "bin" / "opencode",
                Path("/usr/bin/opencode"),
            ]
            # nvm version directories.
            nvm_dir = home / ".nvm" / "versions" / "node"
            if nvm_dir.exists():
                for node_ver in sorted(nvm_dir.iterdir(), reverse=True):
                    p = node_ver / "bin" / "opencode"
                    if p.exists():
                        candidates.insert(0, p)
                        break
            # fnm version directories.
            fnm_dir = home / ".local" / "share" / "fnm" / "node-versions"
            if not fnm_dir.exists():
                fnm_dir = home / "Library" / "Application Support" / "fnm" / "node-versions"
            if fnm_dir.exists():
                for node_ver in sorted(fnm_dir.iterdir(), reverse=True):
                    p = node_ver / "installation" / "bin" / "opencode"
                    if p.exists():
                        candidates.insert(0, p)
                        break

        for path in candidates:
            if path.exists():
                return str(path)

        return "opencode"

    def build_run_cmd(self, agent, prompt, model=None):
        cmd_path = self.get_command_path()
        if sys.platform == "win32":
            cmd = ['cmd', '/c', cmd_path, 'run', '--agent', f'openharness-{agent}']
        else:
            cmd = [cmd_path, 'run', '--agent', f'openharness-{agent}']

        if model:
            cmd.extend(['--model', model])

        cmd.append(prompt)
        return cmd

    def get_config_dir(self):
        config_dir = Path.home() / ".config" / "opencode"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def get_agents_dir(self):
        agents_dir = self.get_config_dir() / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    def install_agents(self, src_dir):
        """Copy agent markdown files into `~/.config/opencode/agents/`."""
        agents_dir = self.get_agents_dir()
        copied = []

        agent_mapping = {
            "orchestrator.md": "openharness-orchestrator.md",
            "initializer.md": "openharness-initializer.md",
            "coder.md": "openharness-coder.md",
            "tester.md": "openharness-tester.md",
            "fixer.md": "openharness-fixer.md",
            "reviewer.md": "openharness-reviewer.md",
        }

        for src_name, dst_name in agent_mapping.items():
            src_path = src_dir / src_name
            dst_path = agents_dir / dst_name
            if src_path.exists():
                shutil.copy2(src_path, dst_path)
                copied.append(dst_name)

        for legacy in agents_dir.glob("harnesscode-*.md"):
            try:
                legacy.unlink()
            except OSError:
                pass

        return copied

    def merge_config(self, openharness_config):
        """Merge openHarness agent config into `opencode.json`."""
        config_path = self.get_config_dir() / "opencode.json"

        # Read the existing config first.
        user_config = {}
        if config_path.exists():
            try:
                user_config = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception):
                user_config = {}

        if "agent" not in user_config:
            user_config["agent"] = {}
        if "mcp" not in user_config:
            user_config["mcp"] = {}

        # Remove legacy OpenCode entries from the previous product name.
        for legacy_key in list(user_config["agent"].keys()):
            if isinstance(legacy_key, str) and legacy_key.startswith("harnesscode-"):
                del user_config["agent"][legacy_key]

        _migrate_legacy_openharness_agent_config(user_config)

        # Merge agent config.
        for agent_name, agent_config in openharness_config.get("agent", {}).items():
            if agent_name in user_config["agent"]:
                existing = user_config["agent"][agent_name]
                if isinstance(existing, dict) and isinstance(agent_config, dict):
                    merged = dict(existing)
                    for key, value in agent_config.items():
                        if key == "permission" and key in merged:
                            existing_perm = merged[key]
                            new_perm = value
                            if isinstance(existing_perm, dict) and isinstance(new_perm, dict):
                                merged_perm = dict(existing_perm)
                                for perm_key, perm_value in new_perm.items():
                                    if perm_key not in merged_perm:
                                        merged_perm[perm_key] = perm_value
                                    elif isinstance(merged_perm[perm_key], dict) and isinstance(perm_value, dict):
                                        for sub_key, sub_value in perm_value.items():
                                            if sub_key not in merged_perm[perm_key]:
                                                merged_perm[perm_key][sub_key] = sub_value
                                merged[key] = merged_perm
                            else:
                                merged[key] = new_perm
                        else:
                            merged[key] = value
                    user_config["agent"][agent_name] = merged
                else:
                    user_config["agent"][agent_name] = agent_config
            else:
                user_config["agent"][agent_name] = agent_config

        # Merge MCP config.
        for mcp_name, mcp_config in openharness_config.get("mcp", {}).items():
            user_config["mcp"][mcp_name] = mcp_config

        # Write updated config.
        config_path.write_text(
            json.dumps(user_config, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return user_config

    def uninstall_agents(self):
        """Remove installed agent files and clean `opencode.json`."""
        agents_dir = self.get_agents_dir()
        removed = []
        for f in list(agents_dir.glob("openharness-*.md")) + list(agents_dir.glob("harnesscode-*.md")):
            try:
                f.unlink()
                removed.append(f.name)
            except OSError:
                pass

        # Clean `opencode.json`.
        config_path = self.get_config_dir() / "opencode.json"
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                if "agent" in config:
                    for agent_name in OPENHARNESS_AGENT_NAMES:
                        prefixed_name = f"openharness-{agent_name}"
                        if prefixed_name in config["agent"]:
                            del config["agent"][prefixed_name]
                            removed.append(f"config:{prefixed_name}")
                        legacy_name = f"harnesscode-{agent_name}"
                        if legacy_name in config["agent"]:
                            del config["agent"][legacy_name]
                            removed.append(f"config:{legacy_name}")
                if "mcp" in config and "playwright" in config["mcp"]:
                    del config["mcp"]["playwright"]
                    removed.append("config:mcp/playwright")
                config_path.write_text(
                    json.dumps(config, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
            except Exception:
                pass

        return removed

    def is_installed(self):
        # 1. Environment variable.
        if os.environ.get("OPENCODE_PATH"):
            p = os.environ["OPENCODE_PATH"]
            if os.path.isfile(p):
                return True

        # 2. Search on PATH.
        if shutil.which("opencode"):
            return True

        # 3. Common install locations.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Roaming" / "npm" / "opencode.cmd",
                home / "AppData" / "Local" / "npm-global" / "opencode.cmd",
            ]
        else:
            candidates = [
                home / ".npm-global" / "bin" / "opencode",
                Path("/usr/local/bin/opencode"),
                Path("/opt/homebrew/bin/opencode"),
                home / ".local" / "bin" / "opencode",
                home / ".volta" / "bin" / "opencode",
                home / ".bun" / "bin" / "opencode",
            ]
            nvm_dir = home / ".nvm" / "versions" / "node"
            if nvm_dir.exists():
                for node_ver in sorted(nvm_dir.iterdir(), reverse=True):
                    p = node_ver / "bin" / "opencode"
                    if p.exists():
                        return True

        for path in candidates:
            if path.exists():
                return True

        return False

    def get_available_models(self):
        config_path = self.get_config_dir() / "opencode.json"
        if not config_path.exists():
            return []
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            models = []
            providers = config.get("provider", {})
            disabled = config.get("disabled_providers", [])
            for provider_name, provider_data in providers.items():
                if provider_name in disabled:
                    continue
                provider_models = provider_data.get("models", {})
                for model_name in provider_models.keys():
                    models.append({
                        "id": f"{provider_name}/{model_name}",
                        "provider": provider_name,
                        "model": model_name,
                    })
            return models
        except Exception:
            return []

    def get_install_hint(self):
        lines = [
            "",
            "=" * 60,
            "  [ERROR] opencode is not installed or not in PATH",
            "",
            "  Please install opencode:",
        ]
        if sys.platform == "win32":
            lines += [
                "    scoop install opencode",
                "      or",
                "    choco install opencode",
                "      or",
                "    npm install -g opencode-ai",
            ]
        elif sys.platform == "darwin":
            lines += [
                "    brew install anomalyco/tap/opencode",
                "      or",
                "    npm install -g opencode-ai",
            ]
        else:
            lines += [
                "    npm install -g opencode-ai",
                "      or",
                "    curl -fsSL https://opencode.ai/install | bash",
            ]
        lines += [
            "",
            "  After installation, restart your terminal and retry.",
            "",
            "  If still not working, set the path manually:",
        ]
        if sys.platform == "win32":
            lines.append("    set OPENCODE_PATH=C:\\path\\to\\opencode.cmd")
        else:
            lines.append("    export OPENCODE_PATH=$(which opencode)")
        lines += ["=" * 60, ""]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude Code Backend
# ---------------------------------------------------------------------------

class ClaudeCodeBackend(Backend):
    """Claude Code (`claude`) execution backend."""

    name = "claude"

    def get_command_path(self):
        # 1. Environment variable override.
        if os.environ.get("CLAUDE_PATH"):
            return os.environ["CLAUDE_PATH"]

        # 2. Search on PATH.
        found = shutil.which("claude")
        if found:
            return found

        # 3. Check common install locations per platform.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Local" / "Programs" / "claude-code" / "claude.exe",
                home / "AppData" / "Roaming" / "npm" / "claude.cmd",
                home / "AppData" / "Local" / "npm-global" / "claude.cmd",
                home / ".local" / "bin" / "claude.exe",
            ]
        elif sys.platform == "darwin":
            candidates = [
                Path("/usr/local/bin/claude"),
                Path("/opt/homebrew/bin/claude"),
                home / ".local" / "bin" / "claude",
                home / ".npm-global" / "bin" / "claude",
            ]
        else:
            candidates = [
                Path("/usr/local/bin/claude"),
                home / ".local" / "bin" / "claude",
                home / ".npm-global" / "bin" / "claude",
            ]
            # nvm version directories.
            nvm_dir = home / ".nvm" / "versions" / "node"
            if nvm_dir.exists():
                for node_ver in sorted(nvm_dir.iterdir(), reverse=True):
                    p = node_ver / "bin" / "claude"
                    if p.exists():
                        candidates.insert(0, p)
                        break

        for path in candidates:
            if path.exists():
                return str(path)

        return "claude"

    def build_run_cmd(self, agent, prompt, model=None):
        cmd_path = self.get_command_path()
        # Claude Code agent names use the `openharness-` prefix.
        agent_name = f"openharness-{agent}"

        if sys.platform == "win32":
            cmd = ['cmd', '/c', cmd_path, '--agent', agent_name, '-p']
        else:
            cmd = [cmd_path, '--agent', agent_name, '-p']

        cmd.append(prompt)

        if model:
            cmd.extend(['--model', model])

        # `--dangerously-skip-permissions`: required for unattended automation.
        # `--output-format stream-json --verbose`: stream JSON events in real time
        # so tool calls, results, and assistant messages all emit output promptly,
        # avoiding idle timeouts caused by delayed default `-p` output.
        cmd.extend([
            '--dangerously-skip-permissions',
            '--permission-mode', 'bypassPermissions',
            '--no-session-persistence',
            '--verbose',
            '--output-format', 'stream-json',
        ])
        return cmd

    def get_config_dir(self):
        config_dir = Path.home() / ".claude"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def get_agents_dir(self):
        agents_dir = self.get_config_dir() / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        return agents_dir

    def install_agents(self, src_dir):
        """Read source markdown, add YAML frontmatter, and write to `~/.claude/agents/`."""
        agents_dir = self.get_agents_dir()
        copied = []

        agent_mapping = {
            "orchestrator.md": "openharness-orchestrator.md",
            "initializer.md": "openharness-initializer.md",
            "coder.md": "openharness-coder.md",
            "tester.md": "openharness-tester.md",
            "fixer.md": "openharness-fixer.md",
            "reviewer.md": "openharness-reviewer.md",
        }

        for src_name, dst_name in agent_mapping.items():
            src_path = src_dir / src_name
            dst_path = agents_dir / dst_name

            if not src_path.exists():
                continue

            # Read source file content.
            content = src_path.read_text(encoding="utf-8")

            # Derive the agent key by removing the `.md` suffix.
            agent_key = src_name.replace(".md", "")
            frontmatter = CLAUDE_AGENT_FRONTMATTER.get(agent_key, {})

            # Build the output with YAML frontmatter.
            fm_name = frontmatter.get("name", f"openharness-{agent_key}")
            fm_desc = frontmatter.get("description", f"openHarness {agent_key} agent")

            output = f"""---
name: {fm_name}
description: "{fm_desc}"
permissionMode: bypassPermissions
---

{content}"""

            dst_path.write_text(output, encoding="utf-8")
            copied.append(dst_name)

        return copied

    def merge_config(self, openharness_config):
        """Claude Code does not require a JSON config file for agents."""
        # If MCP config is needed later, it can be written to `.mcp.json`.
        # For now, no additional configuration is required.
        return {}

    def uninstall_agents(self):
        """Delete `~/.claude/agents/openharness-*.md`."""
        agents_dir = self.get_agents_dir()
        removed = []
        for f in list(agents_dir.glob("openharness-*.md")) + list(agents_dir.glob("harnesscode-*.md")):
            try:
                f.unlink()
                removed.append(f.name)
            except OSError:
                pass
        return removed

    def is_installed(self):
        # 1. Environment variable.
        if os.environ.get("CLAUDE_PATH"):
            p = os.environ["CLAUDE_PATH"]
            if os.path.isfile(p):
                return True

        # 2. Search on PATH.
        if shutil.which("claude"):
            return True

        # 3. Common install locations.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Local" / "Programs" / "claude-code" / "claude.exe",
                home / "AppData" / "Roaming" / "npm" / "claude.cmd",
            ]
        elif sys.platform == "darwin":
            candidates = [
                Path("/usr/local/bin/claude"),
                Path("/opt/homebrew/bin/claude"),
                home / ".local" / "bin" / "claude",
            ]
        else:
            candidates = [
                Path("/usr/local/bin/claude"),
                home / ".local" / "bin" / "claude",
            ]

        for path in candidates:
            if path.exists():
                return True

        return False

    def get_available_models(self):
        """Return the preset model list supported by Claude Code."""
        return [
            {"id": "sonnet", "provider": "anthropic", "model": "sonnet"},
            {"id": "opus", "provider": "anthropic", "model": "opus"},
            {"id": "haiku", "provider": "anthropic", "model": "haiku"},
        ]

    def get_install_hint(self):
        lines = [
            "",
            "=" * 60,
            "  [ERROR] claude is not installed or not in PATH",
            "",
            "  Please install Claude Code:",
        ]
        if sys.platform == "win32":
            lines += [
                "    npm install -g @anthropic-ai/claude-code",
            ]
        elif sys.platform == "darwin":
            lines += [
                "    brew install claude-code",
                "      or",
                "    npm install -g @anthropic-ai/claude-code",
            ]
        else:
            lines += [
                "    npm install -g @anthropic-ai/claude-code",
            ]
        lines += [
            "",
            "  After installation, run 'claude auth login' to authenticate.",
            "",
            "  If still not working, set the path manually:",
        ]
        if sys.platform == "win32":
            lines.append("    set CLAUDE_PATH=C:\\path\\to\\claude.exe")
        else:
            lines.append("    export CLAUDE_PATH=$(which claude)")
        lines += ["=" * 60, ""]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Codex Backend
# ---------------------------------------------------------------------------

class CodexBackend(Backend):
    """OpenAI Codex CLI execution backend."""

    name = "codex"

    def get_command_path(self):
        # 1. Environment variable override.
        if os.environ.get("CODEX_PATH"):
            return os.environ["CODEX_PATH"]

        # 2. Prefer executable/cmd forms on PATH to avoid PowerShell .ps1 policy issues.
        for candidate in ("codex.exe", "codex.cmd", "codex"):
            found = shutil.which(candidate)
            if found:
                return found

        # 3. Check common install locations per platform.
        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Roaming" / "npm" / "codex.cmd",
                home / "AppData" / "Local" / "Programs" / "codex" / "codex.exe",
                home / ".local" / "bin" / "codex.exe",
            ]
        elif sys.platform == "darwin":
            candidates = [
                Path("/usr/local/bin/codex"),
                Path("/opt/homebrew/bin/codex"),
                home / ".local" / "bin" / "codex",
                home / ".npm-global" / "bin" / "codex",
            ]
        else:
            candidates = [
                Path("/usr/local/bin/codex"),
                home / ".local" / "bin" / "codex",
                home / ".npm-global" / "bin" / "codex",
            ]

        for path in candidates:
            if path.exists():
                return str(path)

        return "codex"

    def _compose_agent_prompt(self, agent, prompt):
        installed_agent = self.get_agents_dir() / f"openharness-{agent}.md"
        bundled_agent = Path(__file__).parent / "agents" / f"{agent}.md"

        agent_file = installed_agent if installed_agent.exists() else bundled_agent
        if agent_file.exists():
            agent_instructions = agent_file.read_text(encoding="utf-8")
        else:
            agent_instructions = (
                f"You are acting as the openHarness {agent} agent. "
                "Follow the provided role instructions strictly."
            )

        return (
            f"You are acting as the openHarness {agent} agent.\n\n"
            f"Agent role specification:\n{agent_instructions}\n\n"
            f"Runtime instruction:\n{prompt}"
        )

    def build_run_cmd(self, agent, prompt, model=None):
        cmd_path = self.get_command_path()
        full_prompt = self._compose_agent_prompt(agent, prompt)

        if sys.platform == "win32":
            cmd = ["cmd", "/c", cmd_path, "exec", "--full-auto", "--skip-git-repo-check", "--color", "never"]
        else:
            cmd = [cmd_path, "exec", "--full-auto", "--skip-git-repo-check", "--color", "never"]

        if model:
            cmd.extend(["--model", model])

        cmd.append(full_prompt)
        return cmd

    def get_config_dir(self):
        return Path.home() / ".codex"

    def get_agents_dir(self):
        return self.get_config_dir() / "agents"

    def install_agents(self, src_dir):
        """Copy agent markdown files into `~/.codex/agents/`."""
        agents_dir = self.get_agents_dir()
        agents_dir.mkdir(parents=True, exist_ok=True)
        copied = []

        agent_mapping = {
            "orchestrator.md": "openharness-orchestrator.md",
            "initializer.md": "openharness-initializer.md",
            "coder.md": "openharness-coder.md",
            "tester.md": "openharness-tester.md",
            "fixer.md": "openharness-fixer.md",
            "reviewer.md": "openharness-reviewer.md",
        }

        for src_name, dst_name in agent_mapping.items():
            src_path = src_dir / src_name
            dst_path = agents_dir / dst_name
            if src_path.exists():
                shutil.copy2(src_path, dst_path)
                copied.append(dst_name)

        return copied

    def merge_config(self, openharness_config):
        """Codex does not require a generated config file for openHarness."""
        return {}

    def uninstall_agents(self):
        """Delete `~/.codex/agents/openharness-*.md`."""
        agents_dir = self.get_agents_dir()
        if not agents_dir.exists():
            return []
        removed = []
        for f in list(agents_dir.glob("openharness-*.md")) + list(agents_dir.glob("harnesscode-*.md")):
            try:
                f.unlink()
                removed.append(f.name)
            except OSError:
                pass
        return removed

    def is_installed(self):
        if os.environ.get("CODEX_PATH"):
            p = os.environ["CODEX_PATH"]
            if os.path.isfile(p):
                return True

        for candidate in ("codex.exe", "codex.cmd", "codex"):
            if shutil.which(candidate):
                return True

        home = Path.home()
        if sys.platform == "win32":
            candidates = [
                home / "AppData" / "Roaming" / "npm" / "codex.cmd",
            ]
        elif sys.platform == "darwin":
            candidates = [
                Path("/usr/local/bin/codex"),
                Path("/opt/homebrew/bin/codex"),
                home / ".local" / "bin" / "codex",
            ]
        else:
            candidates = [
                Path("/usr/local/bin/codex"),
                home / ".local" / "bin" / "codex",
            ]

        for path in candidates:
            if path.exists():
                return True

        return False

    def get_available_models(self):
        """Codex CLI handles model discovery internally; return an empty list."""
        return []

    def get_install_hint(self):
        lines = [
            "",
            "=" * 60,
            "  [ERROR] codex is not installed or not in PATH",
            "",
            "  Please install Codex CLI:",
        ]
        if sys.platform == "win32":
            lines += [
                "    npm install -g @openai/codex",
            ]
        elif sys.platform == "darwin":
            lines += [
                "    npm install -g @openai/codex",
            ]
        else:
            lines += [
                "    npm install -g @openai/codex",
            ]
        lines += [
            "",
            "  Then authenticate with:",
            "    codex login",
            "",
            "  If still not working, set the path manually:",
        ]
        if sys.platform == "win32":
            lines.append("    set CODEX_PATH=C:\\path\\to\\codex.cmd")
        else:
            lines.append("    export CODEX_PATH=$(which codex)")
        lines += ["=" * 60, ""]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Backend factory.
# ---------------------------------------------------------------------------

_BACKENDS = {
    "opencode": OpenCodeBackend,
    "claude": ClaudeCodeBackend,
    "codex": CodexBackend,
}


def detect_backend():
    """Auto-detect installed AI backends and return the selected name."""
    installed = [name for name, cls in _BACKENDS.items() if cls().is_installed()]

    if len(installed) == 1:
        return installed[0]
    if len(installed) > 1:
        # Multiple backends are installed; require the user to choose.
        return None
    # If none are installed, default to the historical default backend.
    return DEFAULT_BACKEND


def resolve_backend_name(name=None, project_dir=""):
    """Resolve backend name using the standard precedence order.

    Priority:
    1. Explicit function argument
    2. `OPENHARNESS_BACKEND` environment variable
    3. Project config file
    4. Auto-detection
    5. Default backend
    """
    if name:
        normalized = name.strip().lower()
        if normalized in SUPPORTED_BACKENDS:
            return normalized

    env_backend = os.environ.get("OPENHARNESS_BACKEND", "").strip().lower()
    if env_backend not in SUPPORTED_BACKENDS:
        env_backend = os.environ.get("HARNESSCODE_BACKEND", "").strip().lower()
    if env_backend in SUPPORTED_BACKENDS:
        return env_backend

    try:
        if project_dir:
            try:
                from openharness.utils.config import get_backend_from_config, get_project_config_file
            except ImportError:
                from utils.config import get_backend_from_config, get_project_config_file

            config_path = get_project_config_file(project_dir)
            if config_path.exists():
                config_backend = get_backend_from_config(project_dir)
                if config_backend in SUPPORTED_BACKENDS:
                    return config_backend
    except Exception:
        pass

    detected = detect_backend()
    return detected if detected in SUPPORTED_BACKENDS else DEFAULT_BACKEND


def select_backend_interactive():
    """Interactively choose a backend when multiple options are available."""
    print("\nAvailable AI backends:")
    print("-" * 50)
    options = []
    for name in SUPPORTED_BACKENDS:
        is_installed = _BACKENDS[name]().is_installed()
        status = "installed" if is_installed else "not installed"
        options.append((name, f"{name.ljust(8)}({status})"))

    for i, (_, label) in enumerate(options, 1):
        print(f"  [{i}] {label}")
    print("-" * 50)

    while True:
        try:
            choice = input("\nSelect a backend (enter number, default 1): ").strip()
            if not choice:
                return options[0][0]
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1][0]
            else:
                print(f"Invalid number, please enter 1-{len(options)}")
        except ValueError:
            print("Please enter a valid number")
        except EOFError:
            print("\nNo interactive input detected, using default backend.")
            return options[0][0]
        except KeyboardInterrupt:
            print("\nCancelled")
            sys.exit(0)


def get_backend(name=None):
    """Return a backend instance.

    Priority:
    1. Explicit `name` argument
    2. `OPENHARNESS_BACKEND` environment variable
    3. Auto-detection
    4. Default to `opencode`
    """
    name = resolve_backend_name(name)

    name = name.strip().lower()
    cls = _BACKENDS.get(name)
    if cls is None:
        print(f"[openHarness] Unknown backend: {name}, falling back to {DEFAULT_BACKEND}")
        cls = _BACKENDS[DEFAULT_BACKEND]

    return cls()
