#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys

# Standard GPTK Controller-Mapping für R36S / PortMaster (World of Padman)
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

def main():
    print("=== Starte ARM64 Patch & Build Prozess ===")
    
    work_dir = os.getcwd()
    build_dir = os.path.join(work_dir, "build")
    dist_dir = os.path.join(work_dir, "dist", "ports", "worldofpadman")
    ports_root = os.path.join(work_dir, "dist", "ports")
    
    os.makedirs(build_dir, exist_ok=True)
    os.makedirs(dist_dir, exist_ok=True)

    # 1. CMake Konfiguration und Build
    print("-> Konfiguriere CMake...")
    subprocess.run([
        "cmake", "-B", build_dir, "-S", work_dir,
        "-DCMAKE_BUILD_TYPE=Release",
        "-DUSE_INTERNAL_LIBS=OFF"
    ], check=True)

    print("-> Kompiliere Binaries...")
    subprocess.run(["cmake", "--build", build_dir, "-j", str(os.cpu_count() or 2)], check=True)

    # 2. GPTK Datei direkt ins Artifact schreiben
    gptk_path = os.path.join(dist_dir, "worldofpadman.gptk")
    print(f"-> Schreiben der GPTK-Datei nach: {gptk_path}")
    with open(gptk_path, "w", encoding="utf-8") as f:
        f.write(GPTK_CONTENT)

    # 3. Start-Script (.sh) erstellen
    sh_path = os.path.join(ports_root, "World of Padman.sh")
    print(f"-> Schreiben des Start-Skripts nach: {sh_path}")
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write(LAUNCHER_SCRIPT)
    os.chmod(sh_path, 0o755)

    # 4. Erzeugte Binary kopieren
    compiled_binary = os.path.join(build_dir, "wop.aarch64")
    if os.path.exists(compiled_binary):
        dest_bin = os.path.join(dist_dir, "wop.aarch64")
        shutil.copy2(compiled_binary, dest_bin)
        os.chmod(dest_bin, 0o755)
        print(f"-> Binary kopiert nach: {dest_bin}")

    print("=== Build & Packaging erfolgreich abgeschlossen ===")

if __name__ == "__main__":
    main()
