#!/usr/bin/env python3
"""
World of Padman - ARM64/RK3326-Build (R36S), angelehnt an das
Smokin'-Guns-Projekt: native .so-Module (kein QVM), natives GL4ES,
natives SDL statt Uebersetzungsschicht wo moeglich.

WICHTIGER STAND: World of PADMAN baut ueber CMake (bestaetigt gegen das
echte Repo-README), nicht ueber eine klassische ioquake3-Makefile wie
Smokin' Guns. Die exakten CMake-Optionsnamen fuer GLES/native Module
sind NICHT verifiziert - dieses Skript listet sie deshalb per
"cmake -LAH" auf, bevor es irgendetwas konfiguriert, statt Namen zu
raten. Bitte die Ausgabe im ersten Lauf pruefen und ggf. die
markierten TODO-Stellen unten anpassen.
"""

import os
import re
import subprocess
import sys


def run(cmd, cwd=None, check=True):
    print(f"[RUN] {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)


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
        # Bewusst NICHT ergaenzt: -flto (dokumentierte ARM64-Absturzursache
        # bei ioquake3-Engines in diesem Projekt), -mfpu=... (ungueltig
        # unter AArch64).
    )

    # =========================================================
    # SCHRITT 1: GL4ES bauen (identisch zum Smokin'-Guns-Ansatz)
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
    print("[DIAGNOSE] Bitte pruefen, ob es Optionen fuer GLES/native")
    print("[DIAGNOSE] Module gibt (z.B. etwas mit GLES, RENDERER, ARM,")
    print("[DIAGNOSE] NEON) - die TODO-Stellen unten ggf. entsprechend")
    print("[DIAGNOSE] anpassen, statt die aktuell eingetragenen Namen")
    print("[DIAGNOSE] blind zu vertrauen.")
    print("=" * 70)
    run(["cmake", "-S", work_dir, "-B", build_dir, "-LAH"], check=False)
    print("=" * 70)

    cmake_args = [
        "cmake", "-S", work_dir, "-B", build_dir,
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_C_FLAGS={optimize}",
        f"-DCMAKE_CXX_FLAGS={optimize}",
        "-DCMAKE_SYSTEM_PROCESSOR=aarch64",
        # TODO: exakte Bezeichnung im echten Repo per obiger Diagnose
        # verifizieren, falls hier ein Fehler kommt (Option existiert
        # ggf. unter anderem Namen oder gar nicht in diesem Fork-Stand).
        "-DUSE_RENDERER_DLOPEN=ON",
        "-DBUILD_GAME_SO=ON",
        "-DBUILD_GAME_QVM=OFF",
    ]
    run(cmake_args)
    run(["cmake", "--build", build_dir, "-j", str(os.cpu_count() or 2)])

    # =========================================================
    # SCHRITT 3: Ergebnisse einsammeln (find-basiert, keine
    # hartkodierten Dateinamen - Namenskonvention von WoP nicht
    # 1:1 identisch mit Smokin' Guns verifiziert)
    # =========================================================
    print("[INFO] Gefundene Binaries/Module nach dem Build:")
    for root, _, files in os.walk(build_dir):
        for f in files:
            if f.endswith(".so") or (os.access(os.path.join(root, f), os.X_OK)
                                      and not f.endswith((".cmake", ".txt", ".o"))):
                full = os.path.join(root, f)
                print(f"  {full}")
                run(["cp", full, game_out])

    print("[DONE] Build abgeschlossen. Pruefe die DIAGNOSE-Ausgabe oben und")
    print("[DONE] den Inhalt von out/game - falls dort keine sinnvolle Client-")
    print("[DONE] Binary und keine Renderer-/Game-.so-Dateien auftauchen,")
    print("[DONE] muessen die TODO-markierten CMake-Optionen oben korrigiert")
    print("[DONE] werden - dafuer die DIAGNOSE-Liste der echten cmake -LAH-")
    print("[DONE] Ausgabe verwenden, nicht raten.")


if __name__ == "__main__":
    main()
