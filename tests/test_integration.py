import tempfile, os
from src.nuget_scanner import check_all_projects

def test_integration_with_blocked_package():
    with tempfile.TemporaryDirectory() as tmpdir:
        # crear carpeta del proyecto
        projdir = os.path.join(tmpdir, "MyApp")
        os.makedirs(projdir)
        csproj = os.path.join(projdir, "MyApp.csproj")
        open(csproj, "w").write("<Project/>")

        # crear packages.config con un paquete bloqueado
        pkg = os.path.join(projdir, "packages.config")
        with open(pkg, "w") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
            <packages>
            <package id="log4net" version="1.2.10" targetFramework="net472" />
            </packages>""")

        # configuración de bloqueo
        blocked = [{"name": "log4net", "block_on": ["all"], "min_version": "2.0.0"}]

        # whitelist vacía
        wl_projects, wl_nugets = {}, []

        # 👇 movernos al tmpdir para que glob encuentre el .csproj
        cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            ok = check_all_projects(blocked, wl_projects, wl_nugets, "")
            # ahora sí debería dar False porque log4net está bloqueado
            assert not ok
        finally:
            os.chdir(cwd)
