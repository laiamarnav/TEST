import json, sys
from os.path import exists
from src.logger import log_summary

def load_blocked_packages(path: str):
    if not exists(path):
        log_summary(f"ERROR: File not found {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    blocked = data.get("blocked_packages")
    if not isinstance(blocked, list):
        log_summary(f"ERROR: Invalid format in {path}")
        sys.exit(1)

    result = []
    for entry in blocked:
        if isinstance(entry, str):
            result.append({"name": entry.lower(), "block_on": ["all"], "min_version": None})
        elif isinstance(entry, dict) and "name" in entry:
            result.append({
                "name": entry["name"].lower(),
                "block_on": entry.get("block_on", ["all"]),
                "min_version": entry.get("min_version")
            })
        else:
            log_summary(f"ERROR: Invalid blocked package entry {entry}")
            sys.exit(1)
    return result
