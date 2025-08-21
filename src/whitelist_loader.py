import json, sys
from os.path import exists
from src.logger import log_summary

def load_whitelist_data(path: str):
    if not exists(path):
        log_summary(f"ERROR: File not found {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            log_summary(f"ERROR: Invalid JSON in {path}: {e}")
            sys.exit(1)

    project_whitelist = data.get("whitelist_projects", {})
    nuget_whitelist = data.get("whitelist_nugets", [])

    return project_whitelist, nuget_whitelist
