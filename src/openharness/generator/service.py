"""Requirement generation command orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    from openharness.generator.changes import (
        CHANGE_META_FILENAME,
        CHANGE_MISSING_INFO_FILENAME,
        CHANGE_PRD_FILENAME,
        CHANGE_TECHSPEC_FILENAME,
        get_active_change,
        get_change_dir,
        list_changes,
        resolve_target_change_id,
        set_active_change,
        write_change_meta,
    )
    from openharness.generator.context import DEFAULT_OUTPUT_LANGUAGE, extract_project_context
    from openharness.generator.providers import (
        DEFAULT_GENERATOR_PROVIDER,
        GenerationOutcome,
        GenerationRequest,
        get_generator_provider,
        resolve_generator_provider_name,
    )
    from openharness.installer import ensure_input_directories
    from openharness.utils.config import (
        get_generator_model_from_config,
        get_generator_output_lang,
        get_generator_provider_from_config,
    )
except ImportError:
    from generator.changes import (
        CHANGE_META_FILENAME,
        CHANGE_MISSING_INFO_FILENAME,
        CHANGE_PRD_FILENAME,
        CHANGE_TECHSPEC_FILENAME,
        get_active_change,
        get_change_dir,
        list_changes,
        resolve_target_change_id,
        set_active_change,
        write_change_meta,
    )
    from generator.context import DEFAULT_OUTPUT_LANGUAGE, extract_project_context
    from generator.providers import (
        DEFAULT_GENERATOR_PROVIDER,
        GenerationOutcome,
        GenerationRequest,
        get_generator_provider,
        resolve_generator_provider_name,
    )
    from installer import ensure_input_directories
    from utils.config import (
        get_generator_model_from_config,
        get_generator_output_lang,
        get_generator_provider_from_config,
    )


@dataclass
class GenerationFileResult:
    path: Path
    action: str
    description: str


@dataclass
class GenerationRunResult:
    provider: str
    change_id: str
    active_change_file: Path
    written: List[GenerationFileResult] = field(default_factory=list)
    skipped: List[GenerationFileResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _write_text_file(path: Path, content: str, description: str, overwrite: bool) -> GenerationFileResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return GenerationFileResult(path, "skipped", description)
    path.write_text(content, encoding="utf-8")
    return GenerationFileResult(path, "written", description)


def _missing_info_to_markdown(items: List[str]) -> str:
    header = "# Missing Information\n\n"
    if not items:
        return header + "- None\n"
    return header + "\n".join(f"- {item}" for item in items) + "\n"


def generate_documents(
    prompt: str,
    mode: str,
    provider_name: Optional[str] = None,
    overwrite: bool = False,
    model: Optional[str] = None,
    project_dir: str = ".",
    explicit_change_id: str = "",
) -> GenerationRunResult:
    """Generate Harness SDD change documents and write them to disk."""
    ensure_input_directories(project_dir)

    config_provider = get_generator_provider_from_config(project_dir)
    resolved_provider_name = resolve_generator_provider_name(provider_name, config_provider)
    resolved_model = model or get_generator_model_from_config(project_dir)
    output_language = get_generator_output_lang(project_dir) or DEFAULT_OUTPUT_LANGUAGE
    target_change_id = resolve_target_change_id(project_dir, prompt, mode, explicit_change_id)

    context = extract_project_context(project_dir, prompt, output_language=output_language)
    provider = get_generator_provider(resolved_provider_name)

    outcome: GenerationOutcome
    if not provider.is_available() and resolved_provider_name == DEFAULT_GENERATOR_PROVIDER:
        fallback_provider = get_generator_provider("template")
        outcome = fallback_provider.generate(
            GenerationRequest(prompt=prompt, mode=mode, overwrite=overwrite, model=resolved_model),
            context,
        )
        outcome.warnings.append(
            f"Requested default provider '{resolved_provider_name}' was unavailable. Fell back to template provider."
        )
    else:
        outcome = provider.generate(
            GenerationRequest(prompt=prompt, mode=mode, overwrite=overwrite, model=resolved_model),
            context,
        )

    project_path = Path(project_dir).resolve()
    change_dir = get_change_dir(project_dir, target_change_id)
    result = GenerationRunResult(
        provider=outcome.provider,
        change_id=target_change_id,
        active_change_file=set_active_change(project_dir, target_change_id),
        warnings=list(outcome.warnings),
    )

    if mode in ("prd", "gen", "all"):
        tech_stack_path = project_path / "input" / "prd" / "tech-stack.md"
        file_result = _write_text_file(
            tech_stack_path,
            outcome.tech_stack_content,
            "tech stack definition",
            overwrite=False,
        )
        (result.written if file_result.action == "written" else result.skipped).append(file_result)

    change_dir.mkdir(parents=True, exist_ok=True)
    meta_result = _write_text_file(
        change_dir / CHANGE_META_FILENAME,
        write_change_meta(change_dir, target_change_id, outcome.title).read_text(encoding="utf-8"),
        "change metadata",
        overwrite=True,
    )
    result.written.append(meta_result)

    if mode in ("prd", "gen", "all"):
        file_result = _write_text_file(
            change_dir / CHANGE_PRD_FILENAME,
            outcome.prd_content,
            "change PRD",
            overwrite=overwrite,
        )
        (result.written if file_result.action == "written" else result.skipped).append(file_result)

    if mode in ("spec", "gen", "all"):
        file_result = _write_text_file(
            change_dir / CHANGE_TECHSPEC_FILENAME,
            outcome.techspec_content,
            "change techspec",
            overwrite=overwrite,
        )
        (result.written if file_result.action == "written" else result.skipped).append(file_result)

    if outcome.missing_info:
        file_result = _write_text_file(
            change_dir / CHANGE_MISSING_INFO_FILENAME,
            _missing_info_to_markdown(outcome.missing_info),
            "change missing information",
            overwrite=True,
        )
        result.written.append(file_result)
        result.warnings.append(
            f"Captured {len(outcome.missing_info)} missing-information items in input/changes/{target_change_id}/missing-info.md."
        )

    return result


def run_generation_command(
    command_name: str,
    prompt: str,
    provider_name: Optional[str] = None,
    output_mode: Optional[str] = None,
    overwrite: bool = False,
    model: Optional[str] = None,
    project_dir: str = ".",
    explicit_change_id: str = "",
) -> GenerationRunResult:
    """Run a generation CLI command and print a concise summary."""
    mode_map = {
        "prd": "prd",
        "spec": "spec",
        "gen": "gen",
        "generate": "gen",
    }
    mode = output_mode or mode_map.get(command_name, "gen")
    if mode not in ("prd", "spec", "gen", "all"):
        raise ValueError(f"Unsupported output mode: {mode}")

    result = generate_documents(
        prompt=prompt,
        mode=mode,
        provider_name=provider_name,
        overwrite=overwrite,
        model=model,
        project_dir=project_dir,
        explicit_change_id=explicit_change_id,
    )

    print(f"[openHarness] Requirement generation complete via provider: {result.provider}")
    print(f"[openHarness] Active change: {result.change_id}")
    for item in result.written:
        print(f"  [written] {item.path} ({item.description})")
    for item in result.skipped:
        print(f"  [skipped] {item.path} ({item.description})")
    for warning in result.warnings:
        print(f"  [warning] {warning}")

    return result


def show_change(project_dir: str, change_id: str = "") -> Optional[str]:
    """Print the active or target change summary."""
    target = change_id or get_active_change(project_dir)
    if not target:
        print("[openHarness] No active change selected.")
        return None

    change_dir = get_change_dir(project_dir, target)
    if not change_dir.exists():
        print(f"[openHarness] Change not found: {target}")
        return None

    print(f"[openHarness] Change: {target}")
    for file_name in (CHANGE_META_FILENAME, CHANGE_PRD_FILENAME, CHANGE_TECHSPEC_FILENAME, CHANGE_MISSING_INFO_FILENAME):
        path = change_dir / file_name
        status = "present" if path.exists() else "missing"
        print(f"  {file_name}: {status}")
    return target


def list_changes_command(project_dir: str) -> List[str]:
    """Print available changes."""
    changes = list_changes(project_dir)
    active_change = get_active_change(project_dir)
    if not changes:
        print("[openHarness] No changes found in input/changes.")
        return []

    rows = []
    print("[openHarness] Available changes:")
    for change in changes:
        marker = "*" if change.change_id == active_change else " "
        print(f"  {marker} {change.change_id} [{change.status}] {change.title}")
        rows.append(change.change_id)
    return rows
