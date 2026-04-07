import json
from datetime import datetime
from utils.config import get_metrics_file
from utils.project_id import get_or_create_project_id

class Metrics:
    def __init__(self, project_dir: str):
        self.project_id = get_or_create_project_id(project_dir)
        self.metrics_file = get_metrics_file(self.project_id)
        if not self.metrics_file.exists():
            self.metrics_file.write_text("{}")
    
    def record_session(self, agent: str, success: bool, duration: float):
        """Record execution metrics for an agent run."""
        data = json.loads(self.metrics_file.read_text())
        
        if agent not in data:
            data[agent] = {"total": 0, "success": 0, "recent": []}
        
        data[agent]["total"] += 1
        if success:
            data[agent]["success"] += 1
        
        data[agent]["recent"].append({
            "time": datetime.now().isoformat(),
            "success": success,
            "duration": duration
        })
        data[agent]["recent"] = data[agent]["recent"][-50:]
        
        self.metrics_file.write_text(json.dumps(data, indent=2))
    
    def get_success_rate(self, agent: str, recent_n: int = 10) -> float:
        """Return the success rate for the most recent N runs."""
        data = json.loads(self.metrics_file.read_text())
        if agent not in data or not data[agent]["recent"]:
            return 0.0
        recent = data[agent]["recent"][-recent_n:]
        return sum(1 for r in recent if r["success"]) / len(recent)
