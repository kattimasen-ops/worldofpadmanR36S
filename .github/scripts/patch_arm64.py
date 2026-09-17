#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import logging
import platform

# Timestamps & Log-Level konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

GPTK_CONTENT = """\
back = esc
start = enter
a = mouse_left
b = space
x = c
y = r
l1 = mouse_right
l2 = e
r1 = mouse_left
r2 = ctrl
up = w
down = s
left = a
right = d
left_analog_up = w
left_analog_down = s
left_analog_left = a
left_analog_right = d
right_analog_up = mouse_movement_up
right_analog_down = mouse_movement_down
right_analog_left = mouse_movement_left
right_analog_right = mouse_movement_right
deadzone_mode = axial
deadzone = 2000
deadzone_scale = 8
deadzone_delay = 16
"""

LAUNCHER_SCRIPT = """\
#!/bin/bash
XDG_DATA_HOME="$APPDATA"
export XDG_DATA_HOME

GAMEDIR="$4/worldofpadman"
cd "$GAMEDIR" || exit

$GPTOKEYB "wop.aarch64" -c "./worldofpadman.gptk" &
./wop.aarch64 +set fs_basepath "$GAMEDIR" +set com_hunkMegs 128
$ESUDO killall gptokeyb
"""

def run_cmd(cmd, cwd=None):
    """Führt Konsolenbefehle aus und fängt stderr/stdout für maximale Diagnose ab."""
    logging.info(f"Führe aus: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    
    if res.stdout.strip():
        logging.info(f"[STDOUT]\n{res.stdout.strip()}")
    
    if res.returncode != 0:
        logging.error(f"[FEHLER] Befehl fehlgeschlagen mit Exit-Code {res.returncode}")
        logging.error(f"[STDERR]\n{res.stderr.strip()}")
        sys.exit(res.returncode)

def main():
    logging.info("=== DIAGNOSE & BUILD START ===")
    logging.info(f"Python: {sys.version.split()[0]} | OS: {platform.platform()} | Arch: {platform.machine()}")
    logging.info(f"Arbeitsverzeichnis: {os.getcwd()}")
    logging.info(f"Verfügbare CPU-Kerne: {os.cpu_count()}")

    work_dir = os.getcwd()
    build_dir = os.path.join(work_dir, "build")
    dist_dir = os.path.join(work_dir, "dist", "ports", "worldofpadman")
    ports_root = os.path.join(work_dir, "dist", "ports")

    os.makedirs(build_dir, exist_ok=True)
    os.makedirs(dist_dir, exist_ok=True)

    # Sichere ARM64-Optimierungen für den R36S (explizit ohne fehlerhaftes LTO)
    optimizations = "-O3 -march=armv8-a"

    # 1. CMake Konfiguration mit Performance-Flags und korrekten Abhängigkeiten
    run_cmd([
        "cmake", "-B", build_dir, "-S", work_dir,
        "-DCMAKE_BUILD_TYPE=Release",
        "-DUSE_INTERNAL_LIBS=OFF",
        f"-DCMAKE_C_FLAGS={optimizations}",
        f"-DCMAKE_CXX_FLAGS={optimizations}"
    ])

    # 2. Kompilierung
    run_cmd(["cmake", "--build", build_dir, "-j", str(os.cpu_count() or 2)])

    # 3. Dateierstellung & Validierung
    gptk_path = os.path.join(dist_dir, "worldofpadman.gptk")
    with open(gptk_path, "w", encoding="utf-8") as f:
        f.write(GPTK_CONTENT)
    logging.info(f"GPTK-Datei erfolgreich geschrieben ({os.path.getsize(gptk_path)} Bytes)")

    sh_path = os.path.join(ports_root, "World of Padman.sh")
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write(LAUNCHER_SCRIPT)
    os.chmod(sh_path, 0o755)
    logging.info(f"Start-Skript geschrieben und ausführbar gemacht: {sh_path}")

    compiled_bin = os.path.join(build_dir, "wop.aarch64")
    if os.path.exists(compiled_bin):
        dest_bin = os.path.join(dist_dir, "wop.aarch64")
        shutil.copy2(compiled_bin, dest_bin)
        os.chmod(dest_bin, 0o755)
        
        # Sicheres Stripping zur Reduzierung der Dateigröße
        run_cmd(["strip", "--strip-unneeded", dest_bin])
        
        logging.info(f"Binary verifiziert, optimiert & kopiert: {dest_bin} ({os.path.getsize(dest_bin)} Bytes)")
    else:
        logging.error("CRITICAL: Erzeugte Binary 'wop.aarch64' wurde im Build-Ordner nicht gefunden!")
        sys.exit(1)

    logging.info("=== BUILD ERFOLGREICH ABGESCHLOSSEN ===")

if __name__ == "__main__":
    main()
