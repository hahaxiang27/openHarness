#!/usr/bin/env python3
"""openHarness CLI.

Supports OpenCode, Claude Code, and Codex backends.
"""

import sys
import os

__version__ = "4.1.0"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


def extract_option_arg(option_name):
    """Extract and remove the `<option> value` or `<option>=value` argument."""
    value = None
    args_to_remove = []

    for i, arg in enumerate(sys.argv):
        if arg == option_name and i + 1 < len(sys.argv):
            value = sys.argv[i + 1]
            args_to_remove.extend([i, i + 1])
        elif arg.startswith(f"{option_name}="):
            value = arg.split("=", 1)[1]
            args_to_remove.append(i)

    for i in sorted(args_to_remove, reverse=True):
        sys.argv.pop(i)

    return value


def extract_backend_arg():
    """Extract and remove the `--backend` argument from `sys.argv`."""
    return extract_option_arg("--backend")


def extract_flag(flag_name):
    """Extract and remove a boolean flag from `sys.argv`."""
    found = False
    remaining = []
    for arg in sys.argv:
        if arg == flag_name:
            found = True
            continue
        remaining.append(arg)
    if found:
        sys.argv[:] = remaining
    return found


def main():
    backend_name = extract_backend_arg()
    provider_name = extract_option_arg("--provider")
    output_mode = extract_option_arg("--output-mode")
    model_name = extract_option_arg("--model")
    change_name = extract_option_arg("--change")
    host_name = extract_option_arg("--host")
    port_value = extract_option_arg("--port")
    open_browser = extract_flag("--open")
    overwrite = extract_flag("--overwrite")
    backend_options = "opencode|claude|codex"
    provider_options = "openspec|codex|template"
    
    if len(sys.argv) < 2:
        print("openHarness v" + __version__)
        print("")
        print(
            "Usage: oph [init|start|status|restore|uninstall|prd|spec|gen|change|monitor] "
            f"[--backend {backend_options}] [--provider {provider_options}]"
        )
        print("")
        print("Commands:")
        print("  init      Initialize project configuration (interactive)")
        print("  start     Start development loop")
        print("  status    Show project status and metrics")
        print("  restore   Restore config files from backup (before PR)")
        print("  uninstall Remove openHarness agent files and config")
        print("  prd       Generate a change PRD from a natural-language request")
        print("  spec      Generate a change techspec from a natural-language request")
        print("  gen       Generate the full SDD + Harness change bundle")
        print("  change    Manage active change selection")
        print("  monitor   Launch a read-only local monitoring page")
        print("")
        print("Options:")
        print("  --backend   Specify AI backend: opencode (default), claude, or codex")
        print("  --provider  Specify generator provider: openspec (default), codex, or template")
        print("  --output-mode  Override generation scope: prd, spec, or gen")
        print("  --model     Optional generator model override")
        print("  --change    Target change id for spec or gen updates")
        print("  --host      Host for `oph monitor` (default 127.0.0.1)")
        print("  --port      Port for `oph monitor` (default 8765)")
        print("  --open      Open the monitor page in the default browser")
        print("  --overwrite Allow generated files to replace existing files")
        print("  --version   Show version information")
        print("  --help      Show this help message")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command in ["--version", "-v", "version"]:
        print(f"openharness {__version__}")
        sys.exit(0)
    
    if command in ["--help", "-h", "help"]:
        print("openHarness - AI-assisted human-in-the-loop development framework")
        print("")
        print(
            "Usage: oph [init|start|status|restore|uninstall|prd|spec|gen|change|monitor] "
            f"[--backend {backend_options}] [--provider {provider_options}]"
        )
        print("")
        print("Backends:")
        print("  opencode  Use OpenCode (opencode.ai) as AI engine (default)")
        print("  claude    Use Claude Code (Anthropic) as AI engine")
        print("  codex     Use OpenAI Codex CLI as AI engine")
        print("")
        print("Generator Providers:")
        print("  openspec  Generate Harness SDD change docs with the default provider contract")
        print("  codex     Use Codex CLI to draft the change docs, then normalize them")
        print("  template  Use built-in templates without an external model")
        print("")
        print("Examples:")
        print("  oph init                    # Auto-detect backend")
        print("  oph init --backend claude   # Force Claude Code backend")
        print("  oph init --backend codex    # Force Codex backend")
        print("  oph start                   # Use backend from config")
        print("  oph start --backend claude  # Override backend for this run")
        print("  oph prd \"实现登录功能\"        # Create a new change PRD")
        print("  oph spec \"补充登录技术方案\"    # Update the active change techspec")
        print("  oph gen \"实现登录功能\"        # Generate the full change bundle")
        print("  oph change list             # List available changes")
        print("  oph change use login        # Activate a change")
        print("  oph monitor --open          # Launch the local monitoring page")
        sys.exit(0)

    if command == "init":
        from installer import check_and_initialize
        check_and_initialize(backend_name)
        from infinite_dev import init_project
        init_project(backend_name)
    
    elif command == "start":
        from installer import check_and_initialize
        check_and_initialize(backend_name)
        from infinite_dev import main as run_main
        run_main(backend_name)
    
    elif command == "status":
        from installer import check_and_initialize
        check_and_initialize(backend_name)
        from utils.project_id import get_or_create_project_id
        from utils.metrics import Metrics
        from utils.config import get_backend_from_config
        from generator.changes import get_active_change
        
        project_id = get_or_create_project_id(".")
        metrics = Metrics(".")
        current_backend = get_backend_from_config(".")
        active_change = get_active_change(".")
        
        print(f"Project ID: {project_id}")
        print(f"Backend: {current_backend}")
        print(f"Active change: {active_change or '(none)'}")
        print("")
        print("Agent success rates:")
        for agent in ["orchestrator", "coder", "tester", "fixer"]:
            rate = metrics.get_success_rate(agent)
            print(f"  {agent}: {rate:.1%}")
    
    elif command == "restore":
        from installer import check_and_initialize
        check_and_initialize(backend_name)
        from restore_config import main as restore_main
        restore_main()
    
    elif command == "uninstall":
        from installer import check_and_initialize
        check_and_initialize(backend_name)
        from installer import uninstall
        uninstall()

    elif command == "change":
        from installer import check_and_initialize
        check_and_initialize(backend_name)
        from generator.changes import get_change_dir, set_active_change
        from generator.service import list_changes_command, show_change

        subcommand = sys.argv[2] if len(sys.argv) > 2 else "list"
        if subcommand == "list":
            list_changes_command(os.getcwd())
        elif subcommand == "use":
            target_change = sys.argv[3].strip() if len(sys.argv) > 3 else ""
            if not target_change:
                print("Usage: oph change use <change-id>")
                sys.exit(1)
            if not get_change_dir(os.getcwd(), target_change).exists():
                print(f"[openHarness] Change not found: {target_change}")
                sys.exit(1)
            set_active_change(os.getcwd(), target_change)
            print(f"[openHarness] Active change set to: {target_change}")
            show_change(os.getcwd(), target_change)
        elif subcommand == "show":
            target_change = sys.argv[3].strip() if len(sys.argv) > 3 else ""
            show_change(os.getcwd(), target_change)
        else:
            print("Usage: oph change [list|use <change-id>|show [change-id]]")
            sys.exit(1)

    elif command == "monitor":
        from monitor import serve_monitor

        host = host_name or "127.0.0.1"
        try:
            port = int(port_value) if port_value else 8765
        except ValueError:
            print("[openHarness] `--port` must be an integer.")
            sys.exit(1)

        serve_monitor(
            project_dir=os.getcwd(),
            host=host,
            port=port,
            open_browser=open_browser,
        )

    elif command in ("prd", "spec", "gen", "generate"):
        request_text = " ".join(sys.argv[2:]).strip()
        if command == "generate":
            print("[openHarness] `oph generate` is deprecated. Use `oph gen` instead.")
            command = "gen"
        if not request_text:
            print(f"Usage: oph {command} \"<natural language requirement>\" [--provider {provider_options}]")
            sys.exit(1)

        from generator.service import run_generation_command

        run_generation_command(
            command_name=command,
            prompt=request_text,
            provider_name=provider_name,
            output_mode=output_mode,
            overwrite=overwrite,
            model=model_name,
            project_dir=os.getcwd(),
            explicit_change_id=change_name or "",
        )
    
    else:
        print(f"Unknown command: {command}")
        print(
            "Usage: oph [init|start|status|restore|uninstall|prd|spec|gen|change|monitor] "
            f"[--backend {backend_options}] [--provider {provider_options}]"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
