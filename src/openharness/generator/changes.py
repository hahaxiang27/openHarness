"""Change-based SDD helpers for openHarness."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    from openharness.generator.providers import slugify_prompt
except ImportError:
    from generator.providers import slugify_prompt


ACTIVE_CHANGE_FILENAME = "active_change"
CHANGE_META_FILENAME = "meta.yaml"
CHANGE_PRD_FILENAME = "prd.md"
CHANGE_TECHSPEC_FILENAME = "techspec.md"
CHANGE_MISSING_INFO_FILENAME = "missing-info.md"


@dataclass
class ChangeInfo:
    change_id: str
    title: str
    status: str
    change_dir: Path
    created_at: str = ""


def get_changes_dir(project_dir: str) -> Path:
    return Path(project_dir).resolve() / "input" / "changes"


def get_change_dir(project_dir: str, change_id: str) -> Path:
    return get_changes_dir(project_dir) / change_id


def get_active_change_file(project_dir: str) -> Path:
    return Path(project_dir).resolve() / ".openharness" / ACTIVE_CHANGE_FILENAME


def get_runtime_input_dir(project_dir: str) -> Path:
    return Path(project_dir).resolve() / ".openharness" / "runtime-input"


def ensure_change_directories(project_dir: str) -> Path:
    changes_dir = get_changes_dir(project_dir)
    changes_dir.mkdir(parents=True, exist_ok=True)
    return changes_dir


def get_active_change(project_dir: str) -> str:
    active_file = get_active_change_file(project_dir)
    if not active_file.exists():
        return ""
    try:
        return active_file.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def set_active_change(project_dir: str, change_id: str) -> Path:
    active_file = get_active_change_file(project_dir)
    active_file.parent.mkdir(parents=True, exist_ok=True)
    active_file.write_text(change_id.strip(), encoding="utf-8")
    return active_file


def build_change_id(prompt: str, project_dir: str, explicit_change_id: str = "") -> str:
    if explicit_change_id:
        return slugify_prompt(explicit_change_id)

    changes_dir = ensure_change_directories(project_dir)
    base_id = slugify_prompt(prompt)
    if not (changes_dir / base_id).exists():
        return base_id

    index = 2
    while True:
        candidate = f"{base_id}-{index}"
        if not (changes_dir / candidate).exists():
            return candidate
        index += 1


def parse_meta_file(change_dir: Path) -> ChangeInfo:
    meta_path = change_dir / CHANGE_META_FILENAME
    title = change_dir.name
    status = "draft"
    created_at = ""

    if meta_path.exists():
        try:
            for raw_line in meta_path.read_text(encoding="utf-8").splitlines():
                if ":" not in raw_line:
                    continue
                key, value = raw_line.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "title":
                    title = value or title
                elif key == "status":
                    status = value or status
                elif key == "created_at":
                    created_at = value
        except Exception:
            pass

    return ChangeInfo(
        change_id=change_dir.name,
        title=title,
        status=status,
        change_dir=change_dir,
        created_at=created_at,
    )


def list_changes(project_dir: str) -> List[ChangeInfo]:
    changes_dir = ensure_change_directories(project_dir)
    entries: List[ChangeInfo] = []
    for change_dir in sorted(changes_dir.iterdir()):
        if change_dir.is_dir():
            entries.append(parse_meta_file(change_dir))
    return entries


def resolve_target_change_id(
    project_dir: str,
    prompt: str,
    command_name: str,
    explicit_change_id: str = "",
) -> str:
    if explicit_change_id:
        return slugify_prompt(explicit_change_id)

    active_change = get_active_change(project_dir)
    if command_name == "spec" and active_change:
        return active_change

    if command_name in ("prd", "gen", "generate"):
        return build_change_id(prompt, project_dir)

    if active_change:
        return active_change

    return build_change_id(prompt, project_dir)


def write_change_meta(change_dir: Path, change_id: str, title: str, status: str = "draft") -> Path:
    meta_path = change_dir / CHANGE_META_FILENAME
    created_at = datetime.now().isoformat(timespec="seconds")
    content = (
        f"change_id: {change_id}\n"
        f"title: {title}\n"
        f"status: {status}\n"
        f"created_at: {created_at}\n"
    )
    meta_path.write_text(content, encoding="utf-8")
    return meta_path


def prepare_runtime_input(project_dir: str) -> Optional[Path]:
    active_change = get_active_change(project_dir)
    if not active_change:
        return None

    change_dir = get_change_dir(project_dir, active_change)
    prd_path = change_dir / CHANGE_PRD_FILENAME
    techspec_path = change_dir / CHANGE_TECHSPEC_FILENAME
    if not prd_path.exists() and not techspec_path.exists():
        return None

    runtime_input_dir = get_runtime_input_dir(project_dir)
    if runtime_input_dir.exists():
        shutil.rmtree(runtime_input_dir)

    prd_dir = runtime_input_dir / "input" / "prd"
    prd_upper_dir = runtime_input_dir / "input" / "PRD"
    techspec_dir = runtime_input_dir / "input" / "techspec"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_upper_dir.mkdir(parents=True, exist_ok=True)
    techspec_dir.mkdir(parents=True, exist_ok=True)

    global_tech_stack = Path(project_dir).resolve() / "input" / "prd" / "tech-stack.md"
    if global_tech_stack.exists():
        shutil.copy2(global_tech_stack, prd_dir / "tech-stack.md")
        shutil.copy2(global_tech_stack, prd_upper_dir / "tech-stack.md")

    if prd_path.exists():
        shutil.copy2(prd_path, prd_dir / "generated-prd.md")
        shutil.copy2(prd_path, prd_upper_dir / "generated-prd.md")

    if techspec_path.exists():
        shutil.copy2(techspec_path, techspec_dir / f"tech-spec-{active_change}.md")

    missing_info_path = change_dir / CHANGE_MISSING_INFO_FILENAME
    if missing_info_path.exists():
        shutil.copy2(missing_info_path, prd_dir / "missing-info.md")
        shutil.copy2(missing_info_path, prd_upper_dir / "missing-info.md")

    return runtime_input_dir


def remove_runtime_input(project_dir: str) -> None:
    runtime_input_dir = get_runtime_input_dir(project_dir)
    if runtime_input_dir.exists():
        shutil.rmtree(runtime_input_dir)
