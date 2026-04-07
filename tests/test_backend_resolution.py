from pathlib import Path

from openharness import backend
from openharness.backend import DEFAULT_BACKEND, get_backend, resolve_backend_name
from openharness.generator.changes import get_active_change, list_changes, prepare_runtime_input
from openharness.generator.providers import DEFAULT_GENERATOR_PROVIDER, resolve_generator_provider_name
from openharness.generator.service import generate_documents
from openharness.utils.config import (
    get_backend_from_config,
    get_generator_output_lang,
    get_generator_provider_from_config,
)


def write_config(project_dir: Path, backend_name: str):
    harness_dir = project_dir / '.openharness'
    harness_dir.mkdir()
    (harness_dir / 'config.yaml').write_text(f'backend: {backend_name}\n', encoding='utf-8')


def test_resolve_backend_name_explicit_wins(tmp_path, monkeypatch):
    write_config(tmp_path, 'opencode')
    monkeypatch.setenv('OPENHARNESS_BACKEND', 'claude')
    assert resolve_backend_name('codex', str(tmp_path)) == 'codex'


def test_resolve_backend_name_env_wins_over_config(tmp_path, monkeypatch):
    write_config(tmp_path, 'opencode')
    monkeypatch.setenv('OPENHARNESS_BACKEND', 'claude')
    assert resolve_backend_name(project_dir=str(tmp_path)) == 'claude'


def test_resolve_backend_name_config_wins_over_detect(tmp_path, monkeypatch):
    write_config(tmp_path, 'codex')
    monkeypatch.delenv('OPENHARNESS_BACKEND', raising=False)
    monkeypatch.setattr(backend, 'detect_backend', lambda: 'claude')
    assert resolve_backend_name(project_dir=str(tmp_path)) == 'codex'


def test_resolve_backend_name_uses_detect_then_default(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENHARNESS_BACKEND', raising=False)
    monkeypatch.setattr(backend, 'detect_backend', lambda: 'codex')
    assert resolve_backend_name(project_dir=str(tmp_path)) == 'codex'

    monkeypatch.setattr(backend, 'detect_backend', lambda: None)
    assert resolve_backend_name(project_dir=str(tmp_path)) == DEFAULT_BACKEND


def test_get_backend_from_config_supports_codex(tmp_path, monkeypatch):
    write_config(tmp_path, 'codex')
    monkeypatch.delenv('OPENHARNESS_BACKEND', raising=False)
    assert get_backend_from_config(str(tmp_path)) == 'codex'


def test_get_backend_returns_codex_backend():
    assert get_backend('codex').name == 'codex'


def test_resolve_generator_provider_name_prefers_explicit_then_config():
    assert resolve_generator_provider_name('template', 'openspec') == 'template'
    assert resolve_generator_provider_name(None, 'codex') == 'codex'
    assert resolve_generator_provider_name(None, None) == 'openspec'


def test_generator_config_fields_are_read(tmp_path):
    harness_dir = tmp_path / '.openharness'
    harness_dir.mkdir()
    (harness_dir / 'config.yaml').write_text(
        'generator_provider: codex\n'
        'generator_output_lang: zh-CN\n',
        encoding='utf-8',
    )
    assert get_generator_provider_from_config(str(tmp_path)) == 'codex'
    assert get_generator_output_lang(str(tmp_path)) == 'zh-CN'


def test_gen_creates_change_bundle_and_activates_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = generate_documents(
        prompt='Implement login flow with localStorage',
        mode='gen',
        provider_name='openspec',
        project_dir=str(tmp_path),
    )

    change_dir = tmp_path / 'input' / 'changes' / result.change_id
    assert result.provider == 'openspec'
    assert (tmp_path / 'input' / 'prd' / 'tech-stack.md').exists()
    assert (change_dir / 'prd.md').exists()
    assert (change_dir / 'techspec.md').exists()
    assert (change_dir / 'meta.yaml').exists()
    assert not (tmp_path / 'openspec').exists()
    assert get_active_change(str(tmp_path)) == result.change_id


def test_spec_updates_active_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = generate_documents(
        prompt='Implement login flow',
        mode='gen',
        provider_name='template',
        project_dir=str(tmp_path),
    )

    second = generate_documents(
        prompt='Add validation rules',
        mode='spec',
        provider_name=DEFAULT_GENERATOR_PROVIDER,
        project_dir=str(tmp_path),
    )

    assert second.change_id == first.change_id
    assert (tmp_path / 'input' / 'changes' / first.change_id / 'techspec.md').exists()


def test_generate_documents_keeps_existing_handwritten_tech_stack(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / 'input' / 'prd'
    input_dir.mkdir(parents=True)
    tech_stack_path = input_dir / 'tech-stack.md'
    tech_stack_path.write_text('# Tech Stack\n\n- Manual content\n', encoding='utf-8')

    result = generate_documents(
        prompt='Implement blog publishing',
        mode='prd',
        provider_name=DEFAULT_GENERATOR_PROVIDER,
        project_dir=str(tmp_path),
    )

    assert result.provider == 'openspec'
    assert tech_stack_path.read_text(encoding='utf-8') == '# Tech Stack\n\n- Manual content\n'
    assert any(item.path == tech_stack_path for item in result.skipped)


def test_change_listing_and_runtime_input_view(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = generate_documents(
        prompt='Implement billing dashboard',
        mode='gen',
        provider_name='template',
        project_dir=str(tmp_path),
    )

    changes = list_changes(str(tmp_path))
    assert len(changes) == 1
    assert changes[0].change_id == result.change_id

    runtime_input = prepare_runtime_input(str(tmp_path))
    assert runtime_input is not None
    assert (runtime_input / 'input' / 'prd' / 'generated-prd.md').exists()
    assert (runtime_input / 'input' / 'PRD' / 'generated-prd.md').exists()
    assert (runtime_input / 'input' / 'techspec' / f'tech-spec-{result.change_id}.md').exists()
