import os, re, glob, fnmatch
from os.path import exists, dirname, join


def find_csproj_files():
    return glob.glob("**/*.csproj", recursive=True)


def _version_nums(v: str):
    main = v.split('-', 1)[0] if v else ""
    parts = re.split(r"[._]", main) if main else []
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    return nums


def version_lt(v1: str, v2: str) -> bool:
    try:
        a = _version_nums(v1)
        b = _version_nums(v2)
        L = max(len(a), len(b))
        if len(a) < L: a += [0] * (L - len(a))
        if len(b) < L: b += [0] * (L - len(b))
        return a < b
    except Exception:
        return False


def is_classic_web_app(csproj_path: str) -> bool:
    try:
        with open(csproj_path, encoding="utf-8", errors="ignore") as f:
            text = f.read().lower()
        return "microsoft.webapplication.targets" in text
    except Exception:
        return False


def uses_packages_config(csproj_path: str) -> bool:
    if exists(join(dirname(csproj_path), "packages.config")):
        return True
    try:
        with open(csproj_path, encoding="utf-8", errors="ignore") as f:
            txt = f.read().lower()
        return ("<packagereference" not in txt) and ("\\packages\\" in txt or "/packages/" in txt or "<hintpath>" in txt)
    except Exception:
        return False


def resolve_whitelist_for_project(csproj_path, whitelist_projects):
    project_name = os.path.basename(csproj_path)
    project_key = project_name.lower()
    project_stem = os.path.splitext(project_key)[0]

    merged = list(whitelist_projects.get(project_key, []))

    for k, allowed in whitelist_projects.items():
        if k == project_key:
            continue
        if fnmatch.fnmatch(project_key, k) or fnmatch.fnmatch(project_stem, k):
            merged.extend(allowed)

    return merged


def parse_dotnet_error(stderr: str, csproj_path: str):
    s = (stderr or "").lower()

    if "no assets file was found" in s:
        return ("WARNING",
                f"{csproj_path}: No assets file. Run 'dotnet restore' (o verifica feeds/credenciales).",
                True)

    if "package.config" in s:
        return ("WARNING",
                f"{csproj_path}: Proyecto con packages.config (no soportado por 'dotnet list'). Se omite.",
                True)

    if "microsoft.webapplication.targets" in s:
        hint = "Instala Visual Studio Build Tools 2022 (Web Build Tools) en un agente Windows." if os.name == "nt" else "Ejecuta en agente Windows con VS Build Tools (Web)."
        return ("WARNING",
                f"{csproj_path}: Proyecto ASP.NET clásico sin Web targets. {hint} Se omite.",
                True)

    if "unrecognized option '--vulnerable'" in s or "unrecognized option '--deprecated'" in s or "unrecognized option '--outdated'" in s:
        return ("ERROR",
                f"{csproj_path}: El SDK de .NET es antiguo. Necesitas .NET SDK 5+ para '--vulnerable/--deprecated/--outdated'.",
                False)

    if "unable to load the service index for source" in s or "nu1301" in s or "nu1100" in s:
        return ("ERROR",
                f"{csproj_path}: Problema con las fuentes de NuGet (feed/credenciales/red). Revisa autenticación y accesibilidad de los feeds.",
                False)

    return ("ERROR", f"{csproj_path}: dotnet list package falló. Revisa stderr arriba.", False)
