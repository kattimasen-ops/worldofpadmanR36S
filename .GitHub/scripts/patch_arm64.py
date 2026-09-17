import os
import re
import subprocess
import urllib.request
import urllib.parse
import html.parser
import shutil

class DirectoryParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.files = []
        self.subdirs = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href':
                    if '?' in value or value == '/' or value.startswith('http') or '..' in value:
                        continue
                    if value.endswith('/'):
                        self.subdirs.append(value)
                    elif value.lower().endswith(('.pk3', '.cfg', '.dat', '.txt', '.wad')):
                        self.files.append(value)

def patch_cmakelists(filepath="CMakeLists.txt"):
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} nicht gefunden")
        return False
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    new_content = re.sub(r'cmake_minimum_required\s*\(\s*VERSION\s+3\.\d+\s*\)', 'cmake_minimum_required(VERSION 3.16)', content)
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("[PATCHED] CMake Minimum-Version auf 3.16 angepasst.")
        return True
    return False

def patch_q_platform(filepath="code/qcommon/q_platform.h"):
    if not os.path.exists(filepath):
        print(f"[WARN] {filepath} nicht gefunden")
        return False
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    if "__aarch64__" not in content:
        target = '#error "Architecture not supported"'
        if target in content:
            aarch64_block = (
                "#elif defined(__aarch64__) || defined(_M_ARM64)\n"
                "#define ARCH_STRING \"aarch64\"\n"
                "#define CPUSTRING \"aarch64\"\n"
                "#define ID_LITTLE_ENDIAN 1\n"
                "#define id386 0\n\n"
            )
            content = content.replace(target, aarch64_block + target)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print("[PATCHED] AArch64-Unterstützung zu q_platform.h hinzugefügt.")
            return True
    return False

def inject_neon_math(filepath="code/qcommon/q_math.c"):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    if "arm_neon.h" not in content:
        neon_code = (
            "#if defined(__aarch64__)\n"
            "#include <arm_neon.h>\n"
            "float Q_rsqrt(float number) {\n"
            "    float32x4_t v = vdupq_n_f32(number);\n"
            "    float32x4_t vr = vrsqrteq_f32(v);\n"
            "    vr = vmulq_f32(vr, vrsqrtsq_f32(vmulq_f32(v, vr), vr));\n"
            "    return vgetq_lane_f32(vr, 0);\n"
            "}\n"
            "#else\n"
        )
        new_content, n = re.subn(
            r'(float\s+Q_rsqrt\s*\(\s*float\s+number\s*\)\s*\{)',
            neon_code + r'\1', content, count=1)
        if n > 0:
            new_content, _ = re.subn(
                r'(float\s+Q_rsqrt.*?return.*?\}\n)', r'\1#endif\n',
                new_content, flags=re.DOTALL, count=1)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("[PATCHED] NEON-Version von Q_rsqrt in q_math.c eingefügt.")

def crawl_and_download_mirror(base_url, target_base_dir, current_subpath=""):
    active_url = urllib.parse.urljoin(base_url, current_subpath)
    try:
        req = urllib.request.Request(active_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
        parser = DirectoryParser()
        parser.feed(html_content)
        local_dir = os.path.join(target_base_dir, current_subpath)
        os.makedirs(local_dir, exist_ok=True)
        for filename in sorted(list(set(parser.files))):
            file_url = urllib.parse.urljoin(active_url, filename)
            dest_path = os.path.join(local_dir, filename)
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                continue
            print(f"[DOWNLOAD] {filename}...")
            urllib.request.urlretrieve(file_url, dest_path)
        for subdir in sorted(list(set(parser.subdirs))):
            clean_subdir = subdir.lstrip('/')
            next_subpath = os.path.join(current_subpath, clean_subdir)
            crawl_and_download_mirror(base_url, target_base_dir, next_subpath)
    except Exception as e:
        print(f"[WARN] Download-Fehler bei {active_url}: {e}")

def create_autoexec_cfg(target_dir):
    os.makedirs(target_dir, exist_ok=True)
    cfg_path = os.path.join(target_dir, "autoexec.cfg")
    content = """// M9 Pro (RK3326) World of Padman autoexec.cfg
seta vm_game "0"
seta vm_cgame "0"
seta vm_ui "0"
seta com_hunkMegs "128"
seta com_zoneMegs "32"
seta com_soundMegs "32"
seta r_mode "-1"
seta r_customwidth "640"
seta r_customheight "480"
seta r_fullscreen "1"
seta r_swapInterval "1"
seta r_displayRefresh "60"
seta r_picmip "1"
seta r_texturebits "16"
seta r_colorbits "16"
seta r_depthbits "16"
seta r_dynamiclight "0"
seta r_subdivisions "12"
seta r_lodbias "1"
seta r_fastsky "1"
seta r_drawSun "0"
seta r_flares "0"
seta cg_shadows "0"
seta s_mixahead "0.2"
seta s_khz "22"
"""
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[GENERATE] {cfg_path} erstellt.")

def create_gptk_file(target_dir):
    os.makedirs(target_dir, exist_ok=True)
    gptk_path = os.path.join(target_dir, "wop.gptk")
    content = """back = esc
start = enter
a = space
b = c
x = r
y = e
l1 = mouse2
l2 = f
r1 = mouse1
r2 = space
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
    with open(gptk_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[GENERATE] {gptk_path} erstellt.")

def create_launcher_script(root_artifact_dir):
    os.makedirs(root_artifact_dir, exist_ok=True)
    sh_path = os.path.join(root_artifact_dir, "World of Padman.sh")
    content = """#!/bin/bash
# World of Padman PortMaster Launcher für M9 Pro (RK3326 / Arkos4clones)

XDG_DATA_HOME="$HOME/.local/share"
export XDG_DATA_HOME

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  CONTROLDIR="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  CONTROLDIR="/opt/tools/PortMaster"
else
  CONTROLDIR="/usr/local/bin"
fi

source $CONTROLDIR/control.txt
[ -f "${CONTROLDIR}/modtesting.txt" ] && source "${CONTROLDIR}/modtesting.txt"
get_controls

GAMEDIR="/roms/ports/wop"
if [ ! -d "$GAMEDIR" ]; then
    GAMEDIR="/roms2/ports/wop"
fi
cd "$GAMEDIR"

exec > >(tee "$GAMEDIR/log.txt") 2>&1

# Maximale GL4ES Direct-Translation Flags für Mali-G31 GPU
export LIBGL_FB=2
export LIBGL_ES=2
export LIBGL_GL=21
export LIBGL_SHRINK=2
export LIBGL_VBO=3
export LIBGL_MIPMAP=3
export LIBGL_BATCH=1000
export LIBGL_NOERROR=1
export LIBGL_DEFAULT_EGL=1
export LIBGL_NOINDIRECT=1
export LD_LIBRARY_PATH="$GAMEDIR/libs:$GAMEDIR:$LD_LIBRARY_PATH"

echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

$GPTOKEYB "wop.aarch64" -c "$GAMEDIR/wop.gptk" &

./wop.aarch64 \\
  +set fs_basepath "$GAMEDIR" \\
  +set fs_game wop \\
  +set vm_game 0 \\
  +set vm_cgame 0 \\
  +set vm_ui 0 \\
  +set r_mode -1 \\
  +set r_customwidth 640 \\
  +set r_customheight 480 \\
  +set r_fullscreen 1 \\
  +set com_hunkMegs 128 \\
  +set com_zoneMegs 32 \\
  +set com_soundMegs 32 \\
  +exec autoexec.cfg

$ESUDO killall -9 gptokeyb
echo ondemand | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
"""
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(sh_path, 0o755)
    print(f"[GENERATE] {sh_path} erstellt.")

if __name__ == '__main__':
    subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/work"], check=False)

    patch_cmakelists('CMakeLists.txt')
    patch_q_platform('code/qcommon/q_platform.h')
    inject_neon_math('code/qcommon/q_math.c')

    cpu_count = os.cpu_count() or 2
    
    cflags = (
        "-O3 -mcpu=cortex-a35 -mtune=cortex-a35 -ftree-vectorize -fsimd-cost-model=unlimited "
        "-pipe -fomit-frame-pointer -ffast-math -fno-math-errno -fno-trapping-math "
        "-fno-semantic-interposition -fno-plt -fmerge-all-constants -falign-functions=16 "
        "-falign-loops=16 -DNDEBUG -w -fcommon -mno-outline-atomics -funroll-loops"
    )
    ldflags = "-Wl,-O1 -Wl,--as-needed -Wl,--sort-common"

    build_cmd = (
        f"mkdir -p build && cd build && "
        f"cmake .. -DCMAKE_BUILD_TYPE=Release "
        f"-DUSE_SDL2=ON "
        f"-DBUILD_GAME_SO=ON "
        f"-DBUILD_GAME_QVM=OFF "
        f"-DUSE_VOIP=OFF "
        f"-DUSE_MUMBLE=OFF "
        f"-DCMAKE_C_COMPILER=\"gcc\" "
        f"-DCMAKE_C_FLAGS=\"{cflags}\" "
        f"-DCMAKE_EXE_LINKER_FLAGS=\"{ldflags}\" "
        f"-DCMAKE_SHARED_LINKER_FLAGS=\"{ldflags}\" && "
        f"make -j{cpu_count}"
    )
    print(f"[INFO] Kompiliere World of Padman (SDL2 + Cortex-A35 Native .so), {cpu_count} Jobs")
    subprocess.run(build_cmd, shell=True, check=True)

    artifact_root = "build/artifact"
    dist_game_dir = os.path.join(artifact_root, "wop")
    os.makedirs(dist_game_dir, exist_ok=True)

    mirror_root = "https://files.worldofpadman.net/wop/files/"
    crawl_and_download_mirror(mirror_root, dist_game_dir)

    built_bin_dir = "build"
    for file in os.listdir(built_bin_dir):
        full_p = os.path.join(built_bin_dir, file)
        if file.endswith(".aarch64") or file == "wop.aarch64":
            shutil.copy2(full_p, os.path.join(dist_game_dir, "wop.aarch64"))
            os.chmod(os.path.join(dist_game_dir, "wop.aarch64"), 0o755)

    so_count = 0
    for root, _, files in os.walk(built_bin_dir):
        for f in files:
            if f.endswith(".so"):
                shutil.copy2(os.path.join(root, f), os.path.join(dist_game_dir, f))
                so_count += 1
    print(f"[INFO] {so_count} native .so Shared Libraries eingebunden.")

    create_autoexec_cfg(dist_game_dir)
    create_gptk_file(dist_game_dir)
    create_launcher_script(artifact_root)

    print("[SUCCESS] SDL2-PortMaster-Artefakt erfolgreich erstellt!")
