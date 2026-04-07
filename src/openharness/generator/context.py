"""Project context extraction for requirement generation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

try:
    from openharness.utils.config import load_project_config
except ImportError:
    from utils.config import load_project_config


DEFAULT_OUTPUT_LANGUAGE = "auto"


@dataclass
class ProjectContext:
    """Lightweight context passed into generation providers."""

    project_dir: Path
    config: Dict[str, object]
    existing_prd_files: List[str] = field(default_factory=list)
    existing_techspec_files: List[str] = field(default_factory=list)
    tech_stack_text: str = ""
    readme_excerpt: str = ""
    manifest_summaries: List[str] = field(default_factory=list)
    detected_stack: List[str] = field(default_factory=list)
    output_language: str = DEFAULT_OUTPUT_LANGUAGE


def _read_text_if_exists(path: Path, max_chars: int = 4000) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:max_chars].strip()
    except Exception:
        return ""


def _load_json_if_exists(path: Path) -> Dict[str, object]:
    text = _read_text_if_exists(path, max_chars=12000)
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _detect_stack_from_package_json(project_dir: Path) -> List[str]:
    package_json = _load_json_if_exists(project_dir / "package.json")
    if not package_json:
        return []

    hints: List[str] = ["Node.js", "npm"]
    deps = {}
    for key in ("dependencies", "devDependencies"):
        value = package_json.get(key)
        if isinstance(value, dict):
            deps.update(value)

    if "react" in deps:
        hints.append("React")
    if "vue" in deps:
        hints.append("Vue")
    if "next" in deps:
        hints.append("Next.js")
    if "vite" in deps:
        hints.append("Vite")
    if "typescript" in deps:
        hints.append("TypeScript")

    return hints


def detect_stack_signals(project_dir: Path) -> List[str]:
    """Infer the project's stack from common manifests."""
    detected: List[str] = []

    if (project_dir / "package.json").exists():
        detected.extend(_detect_stack_from_package_json(project_dir))
    if (project_dir / "pyproject.toml").exists():
        detected.extend(["Python", "pyproject"])
    if (project_dir / "requirements.txt").exists():
        detected.extend(["Python", "pip"])
    if (project_dir / "pom.xml").exists():
        detected.extend(["Java", "Maven"])
    if (project_dir / "build.gradle").exists() or (project_dir / "build.gradle.kts").exists():
        detected.extend(["Java", "Gradle"])
    if (project_dir / "Cargo.toml").exists():
        detected.extend(["Rust", "Cargo"])
    if (project_dir / "go.mod").exists():
        detected.extend(["Go"])
    if (project_dir / "index.html").exists():
        detected.extend(["HTML", "CSS", "JavaScript"])

    deduped: List[str] = []
    seen = set()
    for item in detected:
        key = item.lower()
        if key in seen:
            continue
        deduped.append(item)
        seen.add(key)
    return deduped


def _build_manifest_summaries(project_dir: Path) -> List[str]:
    summaries: List[str] = []
    for name in ("package.json", "pyproject.toml", "requirements.txt", "pom.xml", "Cargo.toml", "go.mod"):
        path = project_dir / name
        if not path.exists():
            continue
        text = _read_text_if_exists(path, max_chars=1500)
        if text:
            summaries.append(f"{name}:\n{text}")
    return summaries


def _resolve_output_language(request_text: str, output_language: str) -> str:
    if output_language and output_language != DEFAULT_OUTPUT_LANGUAGE:
        return output_language
    if any("\u4e00" <= char <= "\u9fff" for char in request_text):
        return "zh-CN"
    return "en"


def extract_project_context(project_dir: str, request_text: str, output_language: str = DEFAULT_OUTPUT_LANGUAGE) -> ProjectContext:
    """Collect the minimum useful context for generation providers."""
    project_path = Path(project_dir).resolve()
    input_prd = project_path / "input" / "prd"
    input_techspec = project_path / "input" / "techspec"

    tech_stack_text = _read_text_if_exists(input_prd / "tech-stack.md")
    readme_excerpt = ""
    for candidate in ("README.md", "README_CN.md", "readme.md"):
        readme_excerpt = _read_text_if_exists(project_path / candidate)
        if readme_excerpt:
            break

    existing_prd_files = sorted(
        path.name for path in input_prd.glob("*.md")
    ) if input_prd.exists() else []
    existing_techspec_files = sorted(
        path.name for path in input_techspec.glob("*.md")
    ) if input_techspec.exists() else []

    return ProjectContext(
        project_dir=project_path,
        config=load_project_config(str(project_path)),
        existing_prd_files=existing_prd_files,
        existing_techspec_files=existing_techspec_files,
        tech_stack_text=tech_stack_text,
        readme_excerpt=readme_excerpt,
        manifest_summaries=_build_manifest_summaries(project_path),
        detected_stack=detect_stack_signals(project_path),
        output_language=_resolve_output_language(request_text, output_language),
    )


def summarize_project_context(context: ProjectContext) -> str:
    """Render a compact text summary for AI-backed providers."""
    lines = [
        f"Project directory: {context.project_dir}",
        f"Detected stack: {', '.join(context.detected_stack) if context.detected_stack else 'unknown'}",
        f"Existing PRD files: {', '.join(context.existing_prd_files) if context.existing_prd_files else 'none'}",
        (
            "Existing techspec files: "
            f"{', '.join(context.existing_techspec_files) if context.existing_techspec_files else 'none'}"
        ),
        f"Output language: {context.output_language}",
    ]

    if context.tech_stack_text:
        lines.append("Existing tech-stack.md:\n" + context.tech_stack_text[:1500])
    if context.readme_excerpt:
        lines.append("README excerpt:\n" + context.readme_excerpt[:1500])
    if context.manifest_summaries:
        lines.append("Manifest summaries:\n" + "\n\n".join(context.manifest_summaries[:3]))

    return "\n\n".join(lines)
