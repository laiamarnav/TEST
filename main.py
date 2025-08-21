import argparse, os, sys
from src.logger import log, get_summary
from src.config_loader import load_blocked_packages
from src.whitelist_loader import load_whitelist_data
from src.nuget_scanner import run_dotnet_restore, check_all_projects

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--working-dir", required=True)
    parser.add_argument("--blocked", default="settings/blocked_packages.json")
    parser.add_argument("--whitelist", required=True)
    parser.add_argument("--tag-pr", default="")
    args = parser.parse_args()

    os.chdir(args.working_dir)
    blocked = load_blocked_packages(args.blocked)
    wl_projects, wl_nugets = load_whitelist_data(args.whitelist)

    # Restaurar
    if not run_dotnet_restore(args.working_dir):
        sys.exit(1)

    # Check
    ok = check_all_projects(blocked, wl_projects, wl_nugets, args.tag_pr)

    log("\nSUMMARY")
    for line in get_summary():
        log(line)

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
