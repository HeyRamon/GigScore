#!/usr/bin/env python3
"""Run the GigScore pipeline on the demo cohort."""

import json
from pathlib import Path

# For demo purposes, just load and print the state
state_file = Path(__file__).parent.parent / "app" / "state.json"
state = json.loads(state_file.read_text())

print("GigScore · cohort scorecard · as of Mon Jul 20, 2026 2:00 PM")
print("─" * 62)

for member in state["members"]:
    print(f"{member['name']:<24} GIGSCORE  {member['score']}  ·  {member['band']}")
    print(f"{'':24} {member['updated_line']}")
    print()

print("─" * 62)