#!/usr/bin/env python3
"""
World of Padman - ARM64/RK3326-Build (R36S):
Native .so-Module, natives GL4ES, Mali v11.7 (r11p0) Integration,
automatische Symbol-Bereinigung (strip) und PortMaster-Startskript.
"""

import os
import re
import subprocess
import sys
import urllib.request


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

LAUNCHER_SCRIPT = r"""#!/bin/bash
# PortMaster launch script for World of Padman (RK3326 / M9 Pro, ArkOS4Clone)

GAMEDIR="/roms/ports/worldofpadman"
LOG_FILE="${GAMEDIR}/debug.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# --- PortMaster control setup -------------------------------------------
XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
if [ -d "/opt/system/Tools/PortMaster/" ]; then
    controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
    controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
    controlfolder="$XDG_DATA_HOME/PortMaster"
else
    controlfolder="/roms/ports/PortMaster"
fi

if [ -f "${controlfolder}/control.txt" ]; then
    source "${controlfolder}/control.txt"
    [ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt"
    get_controls
else
    echo "ERROR: ${controlfolder}/control.txt not found - controls will not work." >&2
fi

cd "$GAMEDIR" || exit 1
export HOME="${GAMEDIR}"
mkdir -p "${GAMEDIR}/.wop"

# --- CPU-Performance ----------------------------------------------------
echo "performance" | $ESUDO tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null 2>&1 || true

# --- Grafik: GL4ES & Mali Tweaks (Ohne UI-Batching) --------------------
export LIBGL_ES=2
export LIBGL_GL=1
export LIBGL_NOTEST=1
export LIBGL_FB=1
export LIBGL_FBO=640x480
export LIBGL_NOERROR=1
export LIBGL_FORCE16BITS=1
export LIBGL_VBO=3
export LIBGL_SHRINK=2

export SDL_VIDEODRIVER=kmsdrm
export SDL_AUDIODRIVER=alsa
export LD_LIBRARY_PATH="${GAMEDIR}/libs.aarch64:${GAMEDIR}:${LD_LIBRARY_PATH}"

BINARY="wop.aarch64"
[ -f "./wop.arm64" ] && BINARY="wop.arm64"
[ -f "./wop" ] && BINARY="wop"

# --- Steuerung starten ---------------------------------------------------
$GPTOKEYB "$BINARY" -c "${GAMEDIR}/worldofpadman.gptk" &

# --- Spiel starten mit Engine-Optimierungen ------------------------------
LD_PRELOAD="${GAMEDIR}/libs.aarch64/libGL.so.1:${GAMEDIR}/libs.aarch64/libEGL.so.1" \
  "./$BINARY" \
  +set fs_basepath "${GAMEDIR}" \
  +set fs_homepath "${GAMEDIR}" \
  +set com_zoneMegs 32 \
  +set com_hunkMegs 256 \
  +set com_maxfps 60 \
  +set r_mode -1 \
  +set r_customwidth 640 \
  +set r_customheight 480 \
  +set r_fullscreen 1 \
  +set r_vertexLight 1 \
  +set r_ignorehwgamma 1 \
  +set r_ext_compressed_textures 1 \
  +set r_ext_framebuffer 0 \
  +set r_picmip 2 \
  +set r_lodbias 1 \
  +set r_subdivisions 8 \
  +set r_detailtextures 0 \
  +set r_texturebits 16 \
  +set r_colorbits 16 \
  +set r_depthbits 16 \
  +set r_stencilbits 0 \
  +set r_flares 0 \
  +set r_drawSun 0 \
  +set r_simpleMipMaps 1 \
  +set r_dynamiclight 0 \
  +set r_shadows 0 \
  +set r_fastsky 1 \
  +set r_swapInterval 0 \
  +set cg_shadows 0 \
  +set cg_gibs 0 \
  +set cg_marks 0 \
  +set cg_brassTime 0 \
  +set cg_simpleItems 1 \
  +set cg_forceModel 1 \
  +set s_khz 22 \
  +set s_musicvolume 0 \
  +set vm_game 0 \
  +set vm_cgame 0 \
  +set vm_ui 0

# --- Sauberes Beenden -----------------------------------------------------
unset LD_PRELOAD
unset LD_LIBRARY_PATH
$ESUDO kill -9 $(pidof gptokeyb) 2>/dev/null || true
printf "\033c" > /dev/tty1 2>/dev/null || true
echo "Game exited cleanly."
exit 0
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

    for name in ("libGL.so.1",):
        found = None
        for root, _, files in os.walk(gl4es_dir):
            if name in files:
                found = os.path.join(root, name)
                break
        if found:
            dest = os.path.join(libs_out, name)
            run(["cp", found, dest])
            run(["strip", "--strip-unneeded", dest], check=False)
        else:
            print(f"[WARN] {name} nicht gefunden - gl4es-Build pruefen.")

    # =========================================================
    # SCHRITT 1b: Mali v11.7 (r11p0) Treiber per Python herunterladen
    # =========================================================
    print("[INFO] Lade Mali v11.7 (r11p0) Treiber-Bibliothek herunter...")
    mali_lib_path = os.path.join(libs_out, "libmali.so")
    mali_url = "https://raw.githubusercontent.com/rockchip-linux/libmali/master/lib/aarch64-linux-gnu/libmali-midgard-t860-r11p0-gbm.so"

    try:
        req = urllib.request.Request(mali_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(mali_lib_path, "wb") as out_file:
            out_file.write(response.read())

        if not os.path.exists(mali_lib_path) or os.path.getsize(mali_lib_path) == 0:
            raise RuntimeError("Heruntergeladene libmali.so ist 0 KB groß!")

        for egl_file in ["libEGL.so", "libEGL.so.1", "libGLESv2.so", "libGLESv2.so.2"]:
            target_path = os.path.join(libs_out, egl_file)
            if os.path.exists(target_path) or os.path.islink(target_path):
                os.remove(target_path)
            os.symlink("libmali.so", target_path)
        print(f"[INFO] Mali v11.7 r11p0 ({os.path.getsize(mali_lib_path)} Bytes) und Symlinks erfolgreich angelegt.")
    except Exception as e:
        print(f"[ERROR] Fehler beim Herunterladen/Verknuepfen von Mali v11.7: {e}")
        sys.exit(1)

    # =========================================================
    # SCHRITT 2: World of Padman selbst per CMake konfigurieren
    # =========================================================
    os.makedirs(build_dir, exist_ok=True)

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
    # SCHRITT 3: Ergebnisse einsammeln & Debug-Symbole entfernen
    # =========================================================
    print("[INFO] Sammle Binaries und Module ein...")
    search_paths = [build_dir]
    exclude_dirs = {".git", "gl4es", "out", "work", ".github", "CMakeFiles"}

    collected_files = set()

    for search_path in search_paths:
        for root, dirs, files in os.walk(search_path):
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            
            for f in files:
                full_path = os.path.join(root, f)
                
                if f.endswith((".cmake", ".txt", ".o", ".py", ".sh", ".h", ".c", ".cpp", ".a", ".check_cache")):
                    continue

                is_so = f.endswith(".so")
                is_executable = os.access(full_path, os.X_OK) and not os.path.islink(full_path)
                is_wop_bin = any(k in f.lower() for k in ("wop", "renderer", "cgame", "ui", "qagame"))

                if (is_so or is_executable or is_wop_bin) and os.path.isfile(full_path):
                    if full_path not in collected_files:
                        collected_files.add(full_path)
                        dest = os.path.join(game_out, f)
                        print(f"  Kopiere {full_path} -> {dest}")
                        run(["cp", full_path, dest])
                        run(["strip", "--strip-unneeded", dest], check=False)

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
