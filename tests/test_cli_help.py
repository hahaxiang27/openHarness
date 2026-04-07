import os
import sys

import pytest

from openharness import cli


def test_cli_help_mentions_gen_change_and_monitor(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['hc', '--help'])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert 'opencode|claude|codex' in output
    assert 'Use OpenAI Codex CLI as AI engine' in output
    assert 'hc gen "' in output
    assert 'hc change list' in output
    assert 'hc monitor --open' in output
    assert 'Generate the full change bundle' in output



def test_generate_alias_prints_deprecation_and_runs(monkeypatch, capsys, tmp_path):
    calls = []

    def fake_run_generation_command(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['hc', 'generate', 'Implement', 'login'])

    # `cli` imports `generator.service` with the package directory on sys.path (same as runtime).
    pkg_dir = os.path.dirname(cli.__file__)
    if pkg_dir not in sys.path:
        sys.path.insert(0, pkg_dir)
    import generator.service as service

    monkeypatch.setattr(service, 'run_generation_command', fake_run_generation_command)
    cli.main()
    output = capsys.readouterr().out
    assert 'deprecated' in output
    assert calls[0]['command_name'] == 'gen'



def test_monitor_rejects_invalid_port(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['hc', 'monitor', '--port', 'bad'])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1



def test_init_project_uses_defaults_on_eof(tmp_path, monkeypatch):
    from openharness import infinite_dev

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('builtins.input', lambda prompt='': (_ for _ in ()).throw(EOFError()))
    monkeypatch.setattr(infinite_dev, 'select_branches_for_git_repos', lambda: None)

    project_id = infinite_dev.init_project('codex')

    config_path = tmp_path / '.openharness' / 'config.yaml'
    assert config_path.exists()
    content = config_path.read_text(encoding='utf-8')
    assert f'project_id: {project_id}' in content
    assert 'backend: codex' in content
    assert 'auto_commit: 1' in content
    assert 'generator_provider: openspec' in content
    assert 'generator_output_lang: auto' in content
