#!/usr/bin/env python3
"""openHarness main loop module."""

import os
import random
import subprocess
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from openharness.backend import OpenCodeBackend, get_backend, resolve_backend_name
    from openharness.generator.changes import get_active_change, prepare_runtime_input
    from openharness.knowledge_manager import KnowledgeManager
    from openharness.runtime.context import (
        MAX_NO_DECISION,
        ORCHESTRATOR_PROMPT,
        VALID_AGENTS,
        RuntimeContext,
    )
    from openharness.runtime.execution import (
        get_agent_prompt,
        parse_claude_stream_json as _parse_claude_stream_json,
        run_agent,
        select_model,
    )
    from openharness.runtime.reporting import RuntimeReporter
    from openharness.runtime.state import (
        RuntimeStateStore,
        get_features_from_data,
        get_progress,
        is_false_completion,
        normalize_feature_list,
        normalize_feature_status,
        parse_agent_output_status,
        parse_orchestrator_decision,
        update_same_decision_state,
    )
    from openharness.utils.config import get_learning_dir, get_project_config_file
    from openharness.utils.metrics import Metrics
    from openharness.utils.project_id import get_or_create_project_id
except ImportError:
    from backend import OpenCodeBackend, get_backend, resolve_backend_name
    from generator.changes import get_active_change, prepare_runtime_input
    from knowledge_manager import KnowledgeManager
    from runtime.context import MAX_NO_DECISION, ORCHESTRATOR_PROMPT, VALID_AGENTS, RuntimeContext
    from runtime.execution import (
        get_agent_prompt,
        parse_claude_stream_json as _parse_claude_stream_json,
        run_agent,
        select_model,
    )
    from runtime.reporting import RuntimeReporter
    from runtime.state import (
        RuntimeStateStore,
        get_features_from_data,
        get_progress,
        is_false_completion,
        normalize_feature_list,
        normalize_feature_status,
        parse_agent_output_status,
        parse_orchestrator_decision,
        update_same_decision_state,
    )
    from utils.config import get_learning_dir, get_project_config_file
    from utils.metrics import Metrics
    from utils.project_id import get_or_create_project_id


runtime = RuntimeContext()
state_store = RuntimeStateStore(runtime.paths, lambda *args, **kwargs: None)
reporter = RuntimeReporter(runtime, state_store)


def refresh_runtime(project_dir=None):
    """Refresh shared runtime singletons for the current project directory."""
    global runtime, state_store, reporter
    runtime = RuntimeContext(project_dir=project_dir or os.getcwd())
    state_store = RuntimeStateStore(runtime.paths, lambda *args, **kwargs: None)
    reporter = RuntimeReporter(runtime, state_store)
    state_store.log = reporter.log
    return runtime, state_store, reporter


def prompt_with_default(prompt, default="", empty_message=None):
    """Read user input and fall back to default on EOF."""
    try:
        return input(prompt)
    except EOFError:
        if empty_message:
            print(empty_message)
        return default


def get_opencode_path():
    """Get AI execution engine command path."""
    if runtime.current_backend is not None:
        return runtime.current_backend.get_command_path()
    return OpenCodeBackend().get_command_path()


def read_feature_list():
    return state_store.read_feature_list()


def read_missing_info():
    return state_store.read_missing_info()


def read_test_report():
    return state_store.read_test_report()


def read_review_report():
    return state_store.read_review_report()


def check_skip_possible(blocked_task_args):
    return state_store.check_skip_possible(blocked_task_args)


def check_missing_info_resolved():
    return state_store.check_missing_info_resolved()


def log(message, to_file_only=False):
    return reporter.log(message, to_file_only=to_file_only)


def log_cycle_detail(iteration, agent, args, duration, status, output_summary):
    return reporter.log_cycle_detail(iteration, agent, args, duration, status, output_summary)


def send_im_message(message):
    return reporter.send_im_message(message)


def should_generate_report():
    return reporter.should_generate_report()


def check_and_notify_progress():
    return reporter.check_and_notify_progress()


def generate_dev_report(start_commit=None, report_type="final"):
    return reporter.generate_dev_report(start_commit=start_commit, report_type=report_type)


def find_git_repos(base_dir, max_depth=2):
    """Scan base_dir and subdirectories for Git repositories."""
    repos = []
    base_dir = os.path.abspath(base_dir)

    def scan_dir(current_dir, depth):
        if depth > max_depth:
            return

        git_dir = os.path.join(current_dir, ".git")
        if os.path.isdir(git_dir):
            repos.append(current_dir)

        try:
            for entry in os.listdir(current_dir):
                entry_path = os.path.join(current_dir, entry)
                if os.path.isdir(entry_path) and entry not in (
                    ".git",
                    "node_modules",
                    "__pycache__",
                    ".venv",
                    "venv",
                ):
                    scan_dir(entry_path, depth + 1)
        except (PermissionError, OSError):
            pass

    scan_dir(base_dir, 0)
    return list(set(repos))


def list_branches(repo_dir):
    """List all local and remote branches of a repository."""
    local_branches = []
    remote_branches = []

    try:
        result = subprocess.run(
            ["git", "branch", "--list", "--format=%(refname:short)"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            local_branches = [branch.strip() for branch in result.stdout.splitlines() if branch.strip()]

        result = subprocess.run(
            ["git", "branch", "-r", "--list", "--format=%(refname:short)"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if result.returncode == 0:
            remote_branches = [
                branch.strip()
                for branch in result.stdout.splitlines()
                if branch.strip() and "HEAD" not in branch
            ]
    except Exception as exc:
        print(f"[openHarness] Failed to get branches: {exc}")

    return local_branches, remote_branches


def select_branch_for_repo(repo_dir):
    """Interactively select a branch for a single repository."""
    print(f"\n[Git Repository] {repo_dir}")

    local_branches, remote_branches = list_branches(repo_dir)
    all_branches = []
    seen = set()
    for branch in local_branches + remote_branches:
        if branch not in seen:
            all_branches.append(branch)
            seen.add(branch)

    if not all_branches:
        print("  This repository has no branch information")
        new_branch = prompt_with_default(
            "  Create new branch? Enter new branch name (leave empty to skip): ",
            default="",
            empty_message="  No interactive input detected, skipping branch creation.",
        ).strip()
        if not new_branch:
            return None
        try:
            subprocess.run(
                ["git", "checkout", "-b", new_branch],
                cwd=repo_dir,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            print(f"  Created and switched to branch '{new_branch}'")
            return new_branch
        except subprocess.CalledProcessError as exc:
            print(f"  Failed to create branch: {exc.stderr}")
            return None

    print("  Available branches:")
    for idx, branch in enumerate(all_branches, 1):
        marker = " (current)" if branch in local_branches else ""
        print(f"    {idx}. {branch}{marker}")
    print(f"    {len(all_branches) + 1}. Create new branch")

    while True:
        choice = prompt_with_default(
            "  Please select a branch (enter number): ",
            default="",
            empty_message="  No interactive input detected, keeping current branch.",
        ).strip()
        if not choice:
            return None
        if not choice.isdigit():
            continue
        idx = int(choice)
        if 1 <= idx <= len(all_branches):
            selected = all_branches[idx - 1]
            if selected in remote_branches and selected not in local_branches:
                local_name = selected.split("/", 1)[1] if "/" in selected else selected
                print(f"  Creating local branch '{local_name}' to track '{selected}'")
                try:
                    subprocess.run(
                        ["git", "checkout", "-b", local_name, selected],
                        cwd=repo_dir,
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    return local_name
                except subprocess.CalledProcessError as exc:
                    print(f"  Failed to switch branch: {exc.stderr}")
                    return None
            try:
                subprocess.run(
                    ["git", "checkout", selected],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                return selected
            except subprocess.CalledProcessError as exc:
                print(f"  Failed to switch branch: {exc.stderr}")
                return None

        if idx == len(all_branches) + 1:
            new_branch = prompt_with_default(
                "  Enter a new branch name: ",
                default="",
                empty_message="  No interactive input detected, skipping branch creation.",
            ).strip()
            if not new_branch:
                print("  Branch name cannot be empty")
                continue
            try:
                subprocess.run(
                    ["git", "checkout", "-b", new_branch],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                print(f"  Created and switched to branch '{new_branch}'")
                return new_branch
            except subprocess.CalledProcessError as exc:
                print(f"  Failed to create branch: {exc.stderr}")
                continue

        print("  Invalid selection, please try again")


def select_branches_for_git_repos():
    """Scan the project and let the user choose branches for each repository."""
    print("\n[openHarness] Scanning Git repositories...")

    repos = find_git_repos(runtime.project_dir, max_depth=2)
    if not repos:
        print("  No Git repositories found")
        return

    print(f"  Found {len(repos)} Git repositories")
    repos.sort()

    for repo in repos:
        selected_branch = select_branch_for_repo(repo)
        if selected_branch:
            print(f"  Repository {os.path.basename(repo)} will use branch: {selected_branch}")
        else:
            print(f"  Repository {os.path.basename(repo)} did not select a branch")


def init_project(backend_name=None):
    """Interactively initialize the project configuration."""
    refresh_runtime()

    print("\n[openHarness Initialization]")
    print("Powered by openHarness\n")

    if not backend_name:
        detected = resolve_backend_name(project_dir=runtime.project_dir)
        if detected:
            try:
                from openharness.backend import detect_backend, select_backend_interactive
            except ImportError:
                from backend import detect_backend, select_backend_interactive

            actual_detected = detect_backend()
            if actual_detected is None:
                backend_name = select_backend_interactive()
            else:
                backend_name = detected
                print(f"[openHarness] Auto-detected AI backend: {backend_name}")
        else:
            backend_name = "opencode"
    else:
        print(f"[openHarness] Using specified AI backend: {backend_name}")

    select_branches_for_git_repos()

    auto_commit_input = prompt_with_default(
        "Coder auto-commit mode (0=off, 1=on, default 1): ",
        default="",
        empty_message="No interactive input detected, using default auto-commit mode: 1",
    ).strip()
    auto_commit = int(auto_commit_input) if auto_commit_input.isdigit() and auto_commit_input in ("0", "1") else 1

    os.makedirs(runtime.paths.openharness_dir, exist_ok=True)
    project_id = get_or_create_project_id(runtime.project_dir)

    with open(os.path.join(runtime.paths.openharness_dir, "project_id"), "w", encoding="utf-8") as handle:
        handle.write(project_id)

    config_yaml = f"""# openHarness Configuration
project_id: {project_id}
backend: {backend_name}
auto_commit: {auto_commit}
generator_provider: openspec
generator_output_lang: auto
"""

    config_path = get_project_config_file(runtime.project_dir)
    with open(config_path, "w", encoding="utf-8") as handle:
        handle.write(config_yaml)

    print(f"\nProject initialized: {project_id}")
    print(f"AI backend: {backend_name}")
    print(f"Auto-commit: {auto_commit}")
    print(f"Config file: {config_path}")
    print(f"Project data directory: {runtime.paths.openharness_dir}")

    try:
        from openharness.banner import print_init_completion_banner
    except ImportError:
        from banner import print_init_completion_banner

    print_init_completion_banner(backend_name)

    return project_id


def main(backend_name=None):
    refresh_runtime()

    runtime.current_backend = get_backend(
        resolve_backend_name(backend_name, project_dir=runtime.project_dir)
    )
    select_model(runtime, log)

    runtime.project_id = get_or_create_project_id(runtime.project_dir)
    runtime.metrics = Metrics(runtime.project_dir)
    runtime.knowledge_mgr = KnowledgeManager(runtime.project_dir)

    os.makedirs(runtime.paths.openharness_dir, exist_ok=True)
    active_change = get_active_change(runtime.project_dir)
    runtime_input_dir = prepare_runtime_input(runtime.project_dir)

    log("===== openHarness Started =====")
    log(f"Backend: {runtime.current_backend.name}")
    log(f"Project ID: {runtime.project_id}")
    log(f"Active change: {active_change or 'legacy-flat-input'}")
    log(f"Model: {runtime.selected_model or 'default'}")
    log(f"Config: {get_project_config_file(runtime.project_dir)}")
    log(f"Learning dir: {get_learning_dir(runtime.project_id)}")
    log(f"IDLE_TIMEOUT: {runtime.idle_timeout}s")
    if runtime_input_dir:
        log(f"Runtime input view: {runtime_input_dir}")

    start_commit = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=runtime.project_dir,
            timeout=10,
        )
        if result.returncode == 0:
            start_commit = result.stdout.strip()
            log(f"Start commit: {start_commit[:8]}")
    except Exception:
        pass

    iteration = 1
    last_decision = None
    same_decision_count = 0
    no_decision_count = 0

    while True:
        log(f"===== Cycle {iteration} =====")
        log("Calling orchestrator...")
        orch_output, orch_status, orch_duration = run_agent(
            runtime,
            "orchestrator",
            ORCHESTRATOR_PROMPT,
            f"{iteration}.orch",
            log,
        )
        runtime.metrics.record_session("orchestrator", orch_status == "success", orch_duration)

        if orch_status != "success":
            log("Orchestrator failed, retrying next cycle...")
            time.sleep(random.randint(5, 15))
            iteration += 1
            continue

        next_agent, next_args = parse_orchestrator_decision(orch_output)

        current_decision = f"{next_agent}|{next_args}" if next_agent else ""
        last_decision, same_decision_count = update_same_decision_state(
            last_decision,
            current_decision,
            same_decision_count,
        )
        if current_decision and same_decision_count > 1:
            log(f"[Loop Detection] Same decision repeated {same_decision_count} times")

        if same_decision_count >= 3 and next_agent == "pause_for_human":
            log("[Loop Detection] Same PAUSE decision repeated 3 times...")
            resolved = check_missing_info_resolved()
            if resolved:
                log(f"[Loop Detection] User resolved {len(resolved)} missing_info items")
                same_decision_count = 0
            else:
                skip_result = check_skip_possible(next_args)
                if skip_result["can_skip"]:
                    log(f"[Loop Detection] Skipping to: {skip_result['next_task']}")
                    send_im_message(f"[AUTO SKIP] Continuing with: {skip_result['next_task']}")
                    next_agent = skip_result["agent"]
                    next_args = skip_result["args"]
                    same_decision_count = 0
                else:
                    log("[Loop Detection] All tasks blocked, stopping")
                    send_im_message("[STOPPED] All tasks blocked. Check .openharness/missing_info.json")
                    generate_dev_report(start_commit, report_type="partial")
                    break

        if next_agent == "complete":
            data = read_feature_list()
            test_report = read_test_report()
            review_report = read_review_report()
            is_false, details = is_false_completion(data, test_report, review_report)
            if is_false:
                if details["reason"] == "pending_features":
                    pending_ids = details["pending_ids"]
                    log(f"ORCHESTRATOR PREMATURE COMPLETE! {len(pending_ids)} pending: {pending_ids}")
                    send_im_message(f"[FALSE COMPLETE] {len(pending_ids)} features pending: {pending_ids[:10]}...")
                elif details["reason"] == "test_report_failed":
                    log("ORCHESTRATOR PREMATURE COMPLETE! test_report overall=fail")
                    send_im_message("[FALSE COMPLETE] Test report shows failures")
                else:
                    log("ORCHESTRATOR PREMATURE COMPLETE! review_report overall=fail")
                    send_im_message("[FALSE COMPLETE] Code review shows violations")
                time.sleep(random.randint(5, 15))
                iteration += 1
                continue

            log("PROJECT COMPLETE!")
            progress = get_progress(read_feature_list())
            if progress:
                send_im_message(
                    f"[PROJECT COMPLETE] Final: {progress['passing']}/{progress['total']} "
                    f"({progress['percent']}%)"
                )
            generate_dev_report(start_commit, report_type="final")
            break

        if next_agent == "pause_for_human":
            log("ORCHESTRATOR PAUSED. Check .openharness/missing_info.json")
            send_im_message("[PAUSED] Check .openharness/missing_info.json")
            break

        if not next_agent:
            no_decision_count += 1
            log(f"No valid decision from orchestrator ({no_decision_count}/{MAX_NO_DECISION})")
            if no_decision_count >= MAX_NO_DECISION:
                log("Orchestrator stuck! Forcing initializer to reset state...")
                send_im_message("[ORCHESTRATOR STUCK] Forcing initializer to reset...")
                next_agent = "initializer"
                next_args = ""
                no_decision_count = 0
            else:
                time.sleep(random.randint(5, 15))
                iteration += 1
                continue
        else:
            no_decision_count = 0

        if next_agent not in VALID_AGENTS:
            log(f"Unknown agent '{next_agent}', defaulting to coder")
            next_agent = "coder"

        log(f"Executing: {next_agent} {next_args}".strip())
        log_cycle_detail(iteration, next_agent, next_args, 0, "started", "Agent started execution")

        agent_prompt = get_agent_prompt(runtime, str(next_args) if next_args else "")
        agent_output, agent_status, agent_duration = run_agent(
            runtime,
            next_agent,
            agent_prompt,
            f"{iteration}.{next_agent}",
            log,
        )

        runtime.metrics.record_session(next_agent, agent_status == "success", agent_duration)

        try:
            output_summary = agent_output[:500] if agent_output else "N/A"
            log_cycle_detail(iteration, next_agent, next_args, agent_duration, agent_status, output_summary)
        except Exception as exc:
            log(f"[Error] Failed to write cycle log: {str(exc)}")

        if next_agent == "fixer" and agent_status == "success":
            test_report = read_test_report()
            if test_report:
                layers = test_report.get("layers", {})
                all_issues = []
                static_analysis = layers.get("static_analysis", {})
                for issue in static_analysis.get("issues", []):
                    if issue.get("status") == "pending" and issue.get("suggested_fix"):
                        all_issues.append(issue["suggested_fix"])
                unit_test = layers.get("unit_test", {})
                for result in unit_test.get("results", []):
                    if result.get("status") == "fail" and result.get("suggested_fix"):
                        all_issues.append(result["suggested_fix"])
                if not all_issues:
                    for result in test_report.get("results", []):
                        if result.get("status") == "fail" and result.get("suggested_fix"):
                            all_issues.append(result["suggested_fix"])
                for suggested_fix in all_issues:
                    runtime.knowledge_mgr.save_bug_pattern(
                        suggested_fix.get("summary", ""),
                        suggested_fix.get("location", ""),
                        suggested_fix.get("action", ""),
                    )

        agent_status_result = parse_agent_output_status(agent_output)
        if agent_status_result:
            log(
                f"[Agent Status] {agent_status_result['agent']} - "
                f"{agent_status_result['status']} - {agent_status_result['module']}"
            )

        check_and_notify_progress()

        if "PROJECT COMPLETE" in agent_output.upper() or "ALL FEATURES PASSING" in agent_output.upper():
            data = read_feature_list()
            test_report = read_test_report()
            review_report = read_review_report()
            is_false, details = is_false_completion(data, test_report, review_report)
            if is_false:
                if details["reason"] == "pending_features":
                    pending_ids = details["pending_ids"]
                    log(f"FALSE COMPLETION! {len(pending_ids)} features pending: {pending_ids}")
                    send_im_message(f"[FALSE COMPLETION] {len(pending_ids)} features pending")
                elif details["reason"] == "test_report_failed":
                    log("FALSE COMPLETION! test_report overall=fail")
                    send_im_message("[FALSE COMPLETION] Test report shows failures")
                else:
                    log("FALSE COMPLETION! review_report overall=fail")
                    send_im_message("[FALSE COMPLETION] Code review shows violations")
                time.sleep(random.randint(5, 15))
                iteration += 1
                continue

            log("COMPLETION SIGNAL DETECTED!")
            progress = get_progress(read_feature_list())
            if progress:
                send_im_message(
                    f"[PROJECT COMPLETE] Final: {progress['passing']}/{progress['total']} "
                    f"({progress['percent']}%)"
                )
            generate_dev_report(start_commit, report_type="final")
            break

        time.sleep(random.randint(5, 15))
        iteration += 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        init_project()
    else:
        main()
