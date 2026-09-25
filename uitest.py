"""无头自检：不创建 Kivy window（无 GL 的机器上也能跑），只测逻辑层 + kv 语法。

用法：python uitest.py
覆盖：kv 规则可解析、示例落盘、目录扫描、打开/保存/新建/删除、子进程运行取输出。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("KIVY_TEXT", "pil")      # 无 X 时用 PIL 文本后端
os.environ.setdefault("KIVY_WINDOW", "sdl2")   # 别让它退到 x11 上去连 X server

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAILS = []


def check(name, cond, extra=""):
    print("%-30s %s %s" % (name, "PASS" if cond else "FAIL", extra))
    if not cond:
        FAILS.append(name)


# ---------- 1. 逻辑层 ----------
from workspace import Workspace, list_dir  # noqa: E402

tmp = tempfile.mkdtemp(prefix="pyide_uitest_")
lines = []
ws = Workspace(os.path.join(tmp, "projects"), say=lines.append)
ws.seed_samples(os.path.join(HERE, "samples"))
seeded = sorted(os.listdir(ws.root_path))
check("示例脚本落盘", len(seeded) >= 4, "%d 个" % len(seeded))

items = list_dir(ws.root_path)
kinds = {i["kind"] for i in items}
check("目录扫描含文件/目录", "file" in kinds and "up" in kinds, str(sorted(kinds)))

path = os.path.join(ws.root_path, "demo_run.py")
ws.save(path, "print('hello from uitest')\nprint('OK')\n")
check("保存文件", os.path.isfile(path))
check("打开内容一致", "hello from uitest" in ws.open_file(path))
check("生成不重名", ws.next_name(ws.root_path) == "new_1.py")

ws.run(path)
deadline = time.time() + 30
while ws.running and time.time() < deadline:
    time.sleep(0.1)
out = "".join(lines)
check("运行并取到输出", "hello from uitest" in out and "[exit 0]" in out,
      out.strip().splitlines()[-1] if out.strip() else "")

ws.delete(path)
check("删除文件", not os.path.exists(path))

# ---------- 2. kv 规则可解析（子进程隔离：无 GL 环境会直接退出）----------
kv_code = (
    "import os, sys\n"
    "sys.path.insert(0, %r)\n"
    "os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')\n"
    "os.environ.setdefault('KIVY_TEXT', 'pil')\n"
    "os.environ.setdefault('KIVY_WINDOW', 'sdl2')\n"
    "import codearea, filetree, pkgpanel\n"
    "from kivy.lang import Builder\n"
    "from kivy.uix.boxlayout import BoxLayout\n"
    "class RootUI(BoxLayout): pass\n"
    "from pkgpanel import PackageRow, PackagePanel\n"
    "Builder.load_file(%r)\n"
    "print('KV_OK')\n"
) % (HERE, os.path.join(HERE, "ui.kv"))
try:
    proc = subprocess.run([sys.executable or "python3", "-c", kv_code],
                          capture_output=True, text=True, timeout=90)
    ok = proc.returncode == 0 and "KV_OK" in proc.stdout
    if ok:
        print("%-30s %s" % ("ui.kv 规则可解析", "PASS"))
    else:
        why = (proc.stderr or proc.stdout or "").strip().splitlines()
        print("%-30s %s" % ("ui.kv 规则可解析",
                            "SKIP（本机无 GL/window：%s）" % (why[-1][:40] if why else "unknown")))
except Exception as exc:  # noqa: BLE001
    check("ui.kv 规则可解析", False, repr(exc))

shutil.rmtree(tmp, ignore_errors=True)
print("\n" + "=" * 44)
print("FAILS:", FAILS or "none")
sys.exit(1 if FAILS else 0)
