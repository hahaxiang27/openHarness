from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openharness.backend import CodexBackend  # noqa: E402
from openharness.generator.providers import CodexProvider, GenerationRequest  # noqa: E402


def test_codex_backend_uses_stdin_prompt():
    backend = CodexBackend()

    command = backend.build_run_cmd("coder", "Implement fullscreen button", model="gpt-5")
    stdin_prompt = backend.get_stdin_prompt("coder", "Implement fullscreen button")

    assert command[-1] == "-"
    assert command[0] != "cmd"
    assert "--model" in command
    assert backend.uses_stdin_prompt() is True
    assert "Implement fullscreen button" in stdin_prompt
    assert "openHarness coder agent" in stdin_prompt


def test_codex_backend_prefers_cmd_on_windows(monkeypatch):
    backend = CodexBackend()

    def fake_which(name):
        mapping = {
            "codex.cmd": r"C:\Users\test\AppData\Roaming\npm\codex.cmd",
            "codex.exe": r"C:\Users\test\AppData\Local\Microsoft\WindowsApps\codex.exe",
            "codex": None,
        }
        return mapping.get(name)

    monkeypatch.setattr("openharness.backend.sys.platform", "win32")
    monkeypatch.setattr("openharness.backend.shutil.which", fake_which)

    assert backend.get_command_path().endswith("codex.cmd")


def test_codex_provider_passes_prompt_via_stdin(monkeypatch, tmp_path):
    provider = CodexProvider()
    captured = {}

    class Result:
        returncode = 0
        stdout = '{"title":"t","tech_stack":"x","prd":"y","techspec":"z","missing_info":[]}'

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        captured["cwd"] = kwargs.get("cwd")
        return Result()

    monkeypatch.setattr("openharness.generator.providers.subprocess.run", fake_run)
    monkeypatch.setattr("openharness.generator.providers.summarize_project_context", lambda context: "summary")

    context = type(
        "Context",
        (),
        {
            "project_dir": tmp_path,
            "tech_stack_text": "",
            "detected_stack": ["HTML"],
        },
    )()

    provider._generate_with_codex(
        GenerationRequest(prompt="Add fullscreen button", mode="gen", overwrite=False, model=None),
        context,
    )

    assert captured["cmd"][-1] == "-"
    assert "Add fullscreen button" in captured["input"]
    assert captured["cwd"] == str(tmp_path)
