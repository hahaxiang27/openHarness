import os
from pathlib import Path

try:
    from openharness.backend import DEFAULT_BACKEND, SUPPORTED_BACKENDS
except ImportError:
    from backend import DEFAULT_BACKEND, SUPPORTED_BACKENDS

def get_global_openharness_dir():
    """Return the global openHarness directory (~/.openharness)."""
    openharness_dir = Path.home() / ".openharness"
    openharness_dir.mkdir(parents=True, exist_ok=True)
    (openharness_dir / "projects").mkdir(exist_ok=True)
    return openharness_dir

def get_global_project_dir(project_id: str):
    """Return the global project data directory used for learning data."""
    project_dir = get_global_openharness_dir() / "projects" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir

def get_project_config_file(project_dir: str = ""):
    """Return the project config path (`.openharness/config.yaml`)."""
    if not project_dir:
        project_dir = os.getcwd()
    return Path(project_dir) / ".openharness" / "config.yaml"


def load_project_config(project_dir: str = "") -> dict:
    """Load `.openharness/config.yaml` as a dict when it exists."""
    config_path = get_project_config_file(project_dir)
    if not config_path.exists():
        return {}

    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except ImportError:
        parsed = {}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" not in line or line.strip().startswith("#"):
                        continue
                    key, value = line.split(":", 1)
                    parsed[key.strip()] = value.strip().strip('"').strip("'")
        except Exception:
            return {}
        return parsed
    except Exception:
        return {}

def get_learning_dir(project_id: str):
    """Return the learning data directory."""
    learning_dir = get_global_project_dir(project_id) / "learning"
    learning_dir.mkdir(parents=True, exist_ok=True)
    return learning_dir

def get_metrics_file(project_id: str):
    """Return the metrics file path."""
    return get_learning_dir(project_id) / "metrics.json"

def get_bug_knowledge_dir(project_id: str):
    """Return the bug knowledge base directory."""
    bug_dir = get_learning_dir(project_id) / "docs" / "solutions" / "bugs"
    bug_dir.mkdir(parents=True, exist_ok=True)
    return bug_dir


def get_backend_from_config(project_dir: str = "") -> str:
    """Read the backend setting from `.openharness/config.yaml`.

    Priority:
    1. `OPENHARNESS_BACKEND` environment variable (legacy: `HARNESSCODE_BACKEND`)
    2. `backend` field in `config.yaml`
    3. default to `opencode`

    Returns:
        Backend name from `SUPPORTED_BACKENDS`.
    """
    # 1. Environment variable wins.
    env_backend = os.environ.get("OPENHARNESS_BACKEND", "").strip().lower()
    if env_backend not in SUPPORTED_BACKENDS:
        env_backend = os.environ.get("HARNESSCODE_BACKEND", "").strip().lower()
    if env_backend in SUPPORTED_BACKENDS:
        return env_backend

    # 2. Read from config.yaml.
    config = load_project_config(project_dir)
    backend = str(config.get("backend", "")).strip().lower()
    if backend in SUPPORTED_BACKENDS:
        return backend

    # 3. Default.
    return DEFAULT_BACKEND


def get_generator_provider_from_config(project_dir: str = "") -> str:
    """Return the configured requirement-generator provider name."""
    config = load_project_config(project_dir)
    return str(config.get("generator_provider", "")).strip().lower()


def get_generator_model_from_config(project_dir: str = "") -> str:
    """Return the configured generator model."""
    config = load_project_config(project_dir)
    return str(config.get("generator_model", "")).strip()


def get_generator_output_lang(project_dir: str = "") -> str:
    """Return the configured output language for generated docs."""
    config = load_project_config(project_dir)
    return str(config.get("generator_output_lang", "")).strip()
