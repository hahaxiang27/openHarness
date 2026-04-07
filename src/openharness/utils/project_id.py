import hashlib
from pathlib import Path

def generate_project_id(project_dir: str) -> str:
    """Generate a stable project ID from the project path."""
    abs_path = str(Path(project_dir).resolve())
    hash_val = hashlib.md5(abs_path.encode()).hexdigest()[:8]
    return f"project-{hash_val}"

def get_or_create_project_id(project_dir: str) -> str:
    """Get or create the project ID."""
    openharness_dir = Path(project_dir) / ".openharness"
    id_file = openharness_dir / "project_id"
    
    if id_file.exists():
        return id_file.read_text().strip()
    
    project_id = generate_project_id(project_dir)
    openharness_dir.mkdir(parents=True, exist_ok=True)
    id_file.write_text(project_id)
    
    return project_id
