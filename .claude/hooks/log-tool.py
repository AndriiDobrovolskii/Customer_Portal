#!/usr/bin/env python

import json
import os
import sys
from pathlib import Path
from datetime import datetime

payload = json.load(sys.stdin)

project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
project_root = Path(project_dir) if project_dir else Path(__file__).resolve().parent.parent.parent

log_file = project_root / "docs" / "hooks" / "tool-usage.jsonl"
log_file.parent.mkdir(parents=True, exist_ok=True)

entry = {
    "timestamp": datetime.utcnow().isoformat(),
    "tool": payload.get("tool_name"),
    "tool_input": payload.get("tool_input", {}),
    "session_id": payload.get("session_id")
}

with open(log_file, "a", encoding="utf-8") as f:
    f.write(json.dumps(entry) + "\n")