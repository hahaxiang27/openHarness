#!/usr/bin/env python3
"""openHarness knowledge management module."""

import os
import sys
from datetime import datetime
from pathlib import Path

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from utils.config import get_bug_knowledge_dir
from utils.project_id import get_or_create_project_id


class KnowledgeManager:
    def __init__(self, project_dir: str):
        self.project_id = get_or_create_project_id(project_dir)
        self.bug_dir = get_bug_knowledge_dir(self.project_id)
    
    def save_bug_pattern(self, summary: str, location: str, action: str):
        """Save a bug pattern into the knowledge base."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bug-{timestamp}.md"
        filepath = self.bug_dir / filename
        
        content = f"""# {summary}

> Auto-generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> Project: {self.project_id}

## Location

```
{location}
```

## Solution

{action}

## Tags

- auto-learned
- bug-pattern
"""
        
        filepath.write_text(content, encoding='utf-8')
        return str(filepath)
