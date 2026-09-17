import os
import re
import subprocess
import urllib.request
import urllib.parse
import html.parser

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

def patch_q_platform(filepath="code/qcommon/q_platform.h"):
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found")
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
        if n == 0:
            print("[WARN] Q_rsqrt-Signatur nicht gefunden - NEON-Injection uebersprungen.")
            return
        new_content, n = re.subn(
            r'(float\s+Q_rsqrt.*?return.*?\}\n)', r'\1#endif\n',
            new_content, flags=re.DOTALL, count=1)
        if n == 0:
            print("[WARN] Ende von Q_rsqrt nicht gefunden - #endif fehlt.")
            return
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("[PATCHED] NEON-Version von Q_rsqrt eingefuegt.")

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
            urllib.request.urlretrieve(file_url, dest_path)
        for subdir in sorted(list(set(parser.subdirs))):
            clean_subdir = subdir.lstrip('/')
            next_subpath = os.path.join(current_subpath, clean_subdir)
            crawl_and_download_mirror(base_url, target_base_dir, next_subpath)
    except Exception as e:
        print(f"Error crawling {active_url}: {e}")

if __name__ == '__main__':
    subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/work"], check=False)

    patch_q_platform('code/qcommon/q_platform.h')
    inject_neon_math('code/qcommon/q_math.c')

    cpu_count = os.cpu_count() or 2
    cc = os.environ.get("CC", "cc")

    # Native Shared Libraries (.so) erzwingen & QVM deaktivieren für Cortex-A35
    build_cmd = (
        f"mkdir -p build && cd build && "
        f"cmake .. -DCMAKE_BUILD_TYPE=Release "
        f"-DBUILD_GAME_SO=ON "
        f"-DBUILD_GAME_QVM=OFF "
        f"-DCMAKE_C_COMPILER=\"gcc\" "
        f"-DCMAKE_C_FLAGS=\"-O3 -mcpu=cortex-a35 -mtune=cortex-a35 -pipe -fomit-frame-pointer -ffast-math -ftree-vectorize -fno-math-errno -fno-trapping-math -fno-semantic-interposition -fno-plt -fno-exceptions -fno-rtti -fno-stack-protector -fno-asynchronous-unwind-tables -fmerge-all-constants -falign-functions=16 -falign-loops=16 -DNDEBUG -w -fcommon -fopenmp-simd -flax-vector-conversions -mno-outline-atomics -funroll-loops\" && "
        f"make -j{cpu_count}"
    )
    print(f"[INFO] Kompiliere World of Padman (Native .so) via CMake, {cpu_count} parallele Jobs")
    subprocess.run(build_cmd, shell=True, check=True)

    # Asset-Mirror Download für das wop-Verzeichnis
    mirror_root = "https://files.worldofpadman.net/wop/files/"
    output_mod_dir = "build/wop"
    crawl_and_download_mirror(mirror_root, output_mod_dir)
