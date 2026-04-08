"""Agent execution helpers."""

import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from .context import PROGRESS_FILENAME


SKIP_PATTERNS = [
    r"^Called the \w+ tool",
    r"^<path>",
    r"^<type>",
    r"^<content>",
    r"^\(End of file",
    r"^```",
    r"^output:",
    r"^result:",
    r"^exit_code:",
    r"^duration_ms:",
    r"^#\s*Tool Instructions",
    r"^#\s*Available Tools",
    r"^#\s*Environment",
    r"^#\s*Working directory",
    r"^Platform:",
    r"^Today's date:",
    r"^Is directory a git repo",
    r"^\s*\d+:\s*$",
    r"^\s*$",
]

try:
    import re
except ImportError:  # pragma: no cover
    re = None


def kill_process_tree(pid):
    """Kill process tree cross-platform."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=10,
            )
        else:
            import signal

            os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        pass


def get_env():
    env = os.environ.copy()
    paths = [env.get("PATH", "")]
    if sys.platform == "win32":
        npm_dir = Path.home() / "AppData" / "Roaming" / "npm"
        if npm_dir.exists():
            paths.insert(0, str(npm_dir))
        node_dir = Path("C:/Program Files/nodejs")
        if node_dir.exists():
            paths.insert(0, str(node_dir))
        env["PATH"] = ";".join([p for p in paths if p])
    else:
        env["PATH"] = ":".join([p for p in paths if p])
    return env


def get_available_models(runtime):
    if runtime.current_backend is None:
        return []
    return runtime.current_backend.get_available_models()


def select_model(runtime, log):
    """Interactive model selection."""
    models = get_available_models(runtime)
    if not models:
        log("[Model] No models found in config, using default")
        return None

    print("\nAvailable models:")
    print("-" * 50)
    for i, model in enumerate(models, 1):
        print(f"  [{i}] {model['id']}")
    print("-" * 50)

    while True:
        try:
            choice = input("\nPlease select a model (enter number): ").strip()
            if not choice:
                print("Using default model")
                return None
            idx = int(choice)
            if 1 <= idx <= len(models):
                runtime.selected_model = models[idx - 1]["id"]
                print(f"Selected: {runtime.selected_model}")
                return runtime.selected_model
            print(f"Invalid number, please enter 1-{len(models)}")
        except ValueError:
            print("Please enter a valid number")
        except EOFError:
            print("\nNo interactive input detected, using default model")
            return None
        except KeyboardInterrupt:
            print("\nCancelled")
            sys.exit(0)


def get_agent_prompt(runtime, args=""):
    base_prompt = (
        f"Read .openharness/{PROGRESS_FILENAME} and .openharness/feature_list.json "
        "first, follow your system instructions, complete ONE task, update "
        "progress, then exit cleanly."
    )
    runtime_input_dir = Path(runtime.paths.runtime_input_dir)
    if runtime_input_dir.exists():
        base_prompt += (
            " When `.openharness/runtime-input` exists, treat "
            "`.openharness/runtime-input/input/prd`, "
            "`.openharness/runtime-input/input/PRD`, and "
            "`.openharness/runtime-input/input/techspec` as the active input view. "
            "For any system instruction that references `input/prd`, `input/PRD`, "
            "or `input/techspec`, use the runtime-input mirror instead and ignore "
            "other files under `input/changes`."
        )
    if args:
        return f"{base_prompt} Orchestrator instruction: {args}"
    return base_prompt


def should_skip(line):
    stripped = line.strip()
    if not stripped:
        return True
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, stripped):
            return True
    return False


def filter_and_print(line):
    if should_skip(line):
        return None
    print(line, end="", flush=True)
    return line


def parse_claude_stream_json(line):
    """Parse Claude stream-json output into printable text."""
    stripped = line.strip()
    if not stripped:
        return None, False

    try:
        event = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return line, True

    event_type = event.get("type", "")

    if event_type == "assistant":
        message = event.get("message", {})
        content = message.get("content", [])
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        if texts:
            return "\n".join(texts) + "\n", True
        return None, True

    if event_type == "result":
        result_text = event.get("result", "")
        if result_text:
            return result_text + "\n", True
        return None, True

    if event_type == "tool_use":
        tool_name = event.get("tool", event.get("name", ""))
        return f"[Tool] {tool_name}\n", True

    return None, True


def run_agent(runtime, agent, prompt, iteration, log):
    """Run an agent through the configured backend."""
    cmd = runtime.current_backend.build_run_cmd(agent, prompt, runtime.selected_model)
    stdin_prompt = None
    if runtime.current_backend.uses_stdin_prompt():
        stdin_prompt = runtime.current_backend.get_stdin_prompt(agent, prompt)
    is_claude_stream = runtime.current_backend.name == "claude"

    start_time = time.time()
    output_lines = []
    process = None
    last_output_time = [time.time()]
    timeout_killed = [False]

    def timeout_watcher():
        warned = [False]
        while not timeout_killed[0]:
            time.sleep(10)
            if timeout_killed[0]:
                break
            idle_time = time.time() - last_output_time[0]
            if idle_time > runtime.idle_timeout:
                log(
                    f"Session {iteration} IDLE TIMEOUT (no output for "
                    f"{runtime.idle_timeout}s)! Killing..."
                )
                if process and process.pid:
                    kill_process_tree(process.pid)
                timeout_killed[0] = True
                break
            if idle_time > runtime.idle_timeout - 60 and not warned[0]:
                log(
                    f"[Warning] Session {iteration} approaching timeout "
                    f"({int(idle_time)}s idle)"
                )
                warned[0] = True

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if stdin_prompt is not None else None,
            cwd=runtime.project_dir,
            env=get_env(),
            bufsize=0,
        )

        if stdin_prompt is not None and process.stdin:
            try:
                process.stdin.write(stdin_prompt.encode("utf-8"))
                process.stdin.flush()
            except OSError:
                # Codex may close stdin early after consuming the prompt; keep
                # reading stdout instead of failing the whole agent session.
                pass
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass

        watcher = threading.Thread(target=timeout_watcher, daemon=True)
        watcher.start()

        if process.stdout:
            for raw_line in iter(process.stdout.readline, b""):
                if timeout_killed[0]:
                    break
                if not raw_line:
                    continue
                try:
                    line = raw_line.decode("utf-8", errors="replace")
                except Exception:
                    line = raw_line.decode("latin-1", errors="replace")

                if is_claude_stream:
                    text, is_heartbeat = parse_claude_stream_json(line)
                    if is_heartbeat:
                        last_output_time[0] = time.time()
                    if text:
                        filtered = filter_and_print(text)
                        if filtered:
                            output_lines.append(filtered)
                else:
                    last_output_time[0] = time.time()
                    filtered = filter_and_print(line)
                    if filtered:
                        output_lines.append(filtered)

        if not timeout_killed[0]:
            process.wait(timeout=60)

        output = "".join(output_lines)
        duration = time.time() - start_time

        if timeout_killed[0]:
            log(f"Session {iteration} was killed due to idle timeout.")
            return output, "timeout", duration

        log(f"Session {iteration} completed", to_file_only=True)
        return output, "success", duration

    except subprocess.TimeoutExpired:
        if process and process.pid:
            kill_process_tree(process.pid)
        log(f"Session {iteration} timeout!")
        return "", "timeout", time.time() - start_time
    except FileNotFoundError:
        log(f"Session {iteration} error: {runtime.current_backend.name} command not found!")
        log(runtime.current_backend.get_install_hint())
        log(f"openHarness cannot run without {runtime.current_backend.name}. Exiting.")
        sys.exit(1)
    except Exception as exc:
        log(f"Session {iteration} error: {str(exc)}")
        return "", "error", time.time() - start_time
    finally:
        timeout_killed[0] = True
