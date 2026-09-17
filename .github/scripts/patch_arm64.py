#!/usr/bin/env python3
"""
World of Padman - ARM64/RK3326-Build (R36S), angelehnt an das
Smokin'-Guns-Projekt: native .so-Module (kein QVM), natives GL4ES,
natives SDL statt Uebersetzungsschicht wo moeglich.
"""

import os
import re
import subprocess
import sys


def run(cmd, cwd=None, check=True):
    print(f"[RUN] {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)


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
if [ ! -d "$GAMEDIR" ]; then
  GAMEDIR="$(dirname "$0")"
fi
cd "$GAMEDIR" || exit

export LD_LIBRARY_PATH="$GAMEDIR/libs.aarch64:$GAMEDIR:$LD_LIBRARY_PATH"

BINARY="wop.aarch64"
[ -f "./wop.arm64" ] && BINARY="wop.arm64"
[ -f "./wop" ] && BINARY="wop"

$GPTOKEYB "$BINARY" -c "./worldofpadman.gptk" &
./$BINARY +set fs_basepath "$GAMEDIR" +set com_hunkMegs 128
$ESUDO killall gptokeyb
"""


def main():
    work_dir = os.getcwd()
    gl4es_dir = os.path.join(work_dir, "gl4es")
    build_dir = os.path.join(work_dir, "build")
    out_dir = os.path.join(work_dir, "out")
    libs_out = os.path.join(out_dir, "libs.aarch64")
    game_out = os.path.join(out_dir, "game")
    os.makedirs(libs_out, exist_ok=True)
    os.makedirs(game_out, exist_ok=True)

    run(["git", "config", "--global", "--add", "safe.directory", "*"])

    optimize = (
        "-O3 -mcpu=cortex-a35 -mtune=cortex-a35 -pipe -fomit-frame-pointer "
        "-ffast-math -ftree-vectorize -fno-semantic-interposition -fno-plt "
        "-fno-stack-protector -fno-asynchronous-unwind-tables "
        "-fmerge-all-constants -falign-functions=16 -falign-loops=16 "
        "-DNDEBUG -w -fcommon -mno-outline-atomics -funroll-loops"
    )

    # =========================================================
    # SCHRITT 1: GL4ES bauen
    # =========================================================
    if not os.path.isdir(gl4es_dir):
        run(["git", "clone", "--depth=1", "https://github.com/ptitSeb/gl4es.git", gl4es_dir])
    gl4es_build = os.path.join(gl4es_dir, "build")
    os.makedirs(gl4es_build, exist_ok=True)
    run([
        "cmake", "..",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_C_FLAGS={optimize}",
        "-DNOX11=ON", "-DGLX_STUBS=ON", "-DEGL_WRAPPER=ON", "-DGBM=ON",
        "-DSTATICLIB=OFF", "-DDEFAULT_ES=2", "-DNOERROR=ON",
    ], cwd=gl4es_build)
    run(["make", f"-j{os.cpu_count() or 2}"], cwd=gl4es_build)

    for name in ("libGL.so.1", "libEGL.so.1"):
        found = None
        for root, _, files in os.walk(gl4es_dir):
            if name in files:
                found = os.path.join(root, name)
                break
        if found:
            run(["cp", found, os.path.join(libs_out, name)])
        else:
            print(f"[WARN] {name} nicht gefunden - gl4es-Build pruefen.")

    # =========================================================
    # SCHRITT 2: World of Padman selbst per CMake konfigurieren
    # =========================================================
    os.makedirs(build_dir, exist_ok=True)

    print("=" * 70)
    print("[DIAGNOSE] Verfuegbare CMake-Cache-Variablen (cmake -LAH):")
    print("=" * 70)
    run(["cmake", "-S", work_dir, "-B", build_dir, "-LAH"], check=False)
    print("=" * 70)

    cmake_args = [
        "cmake", "-S", work_dir, "-B", build_dir,
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_C_FLAGS={optimize}",
        f"-DCMAKE_CXX_FLAGS={optimize}",
        "-DCMAKE_SYSTEM_PROCESSOR=aarch64",
        "-DUSE_RENDERER_DLOPEN=ON",
        "-DBUILD_GAME_SO=ON",
        "-DBUILD_GAME_QVM=OFF",
    ]
    run(cmake_args)
    run(["cmake", "--build", build_dir, "-j", str(os.cpu_count() or 2)])

    # =========================================================
    # SCHRITT 3: Ergebnisse einsammeln (aus build_dir UND work_dir,
    # da CMake Binaries/Module teils im Quellverzeichnis ablegt)
    # =========================================================
    print("[INFO] Sammle Binaries und Module ein...")
    search_paths = [build_dir, work_dir]
    exclude_dirs = {".git", "gl4es", "out", "work", "build", ".github"}

    collected_files = set()

    for search_path in search_paths:
        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            
            for f in files:
                full_path = os.path.join(root, f)
                is_so = f.endswith(".so")
                is_executable = os.access(full_path, os.X_OK) and not f.endswith((".cmake", ".txt", ".o", ".py", ".sh", ".h", ".c", ".cpp"))
                is_wop_bin = "wop" in f.lower() or "renderer" in f.lower() or "cgame" in f.lower() or "ui" in f.lower() or "qagame" in f.lower()

                if (is_so or is_executable or is_wop_bin) and os.path.isfile(full_path):
                    if full_path not in collected_files:
                        collected_files.add(full_path)
                        dest = os.path.join(game_out, f)
                        print(f"  Kopiere {full_path} -> {dest}")
                        run(["cp", full_path, dest])

    # =========================================================
    # SCHRITT 4: GPTK und Start-Skript (.sh) für PortMaster erstellen
    # =========================================================
    gptk_path = os.path.join(game_out, "worldofpadman.gptk")
    with open(gptk_path, "w", encoding="utf-8") as f:
        f.write(GPTK_CONTENT)
    print(f"[INFO] GPTK-Datei erstellt: {gptk_path}")

    sh_path_game = os.path.join(game_out, "World of Padman.sh")
    with open(sh_path_game, "w", encoding="utf-8") as f:
        f.write(LAUNCHER_SCRIPT)
    os.chmod(sh_path_game, 0o755)
    print(f"[INFO] Start-Skript erstellt: {sh_path_game}")

    print("[DONE] Build und Paketierung erfolgreich abgeschlossen.")


if __name__ == "__main__":
    main()
