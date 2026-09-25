"""无界面自检：不启动 Kivy，直接验证 runner 与各示例脚本能不能跑。

桌面：  python selftest.py
手机：  用 Pydroid 3 打开本文件运行（先把工作目录设到 pyide/）
判定：  全部 PASS 才 exit 0；pygame 脚本跑 5 秒不崩也算 PASS（无头环境用 dummy 驱动）。
"""
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from runner import ScriptRunner, python_exe  # noqa: E402

SCRIPTS = ["01_numpy_demo.py", "03_pil_thumb.py", "04_env_probe.py"]
AI_SCRIPTS = ["05_ai_image.py", "06_ai_feature.py"]   # 缺 onnxruntime 时记 SKIP，不算失败
GUI_SCRIPT = "02_pygame_touch.py"
TIMEOUT = 60
SKIPPED = []


def run_capture(path, cwd, timeout=TIMEOUT):
    lines = []
    done = threading.Event()

    def on_state(running):
        if not running:  # runner 结束时会回调一次 False
            done.set()

    r = ScriptRunner(on_line=lines.append, on_state=on_state)

    def target():
        r.run(path, cwd=cwd)

    threading.Thread(target=target, daemon=True).start()
    ok = done.wait(timeout)
    if not ok:
        r.stop()
        time.sleep(0.5)
        lines.append("! 超时 %ss，已强制停止" % timeout)
    return "".join(lines), ok


def main():
    print("interpreter:", python_exe())
    print("python     :", sys.version.split()[0])
    results = []

    workdir = tempfile.mkdtemp(prefix="pyide_selftest_")  # 示例脚本写文件只写这里
    for name in SCRIPTS + AI_SCRIPTS:
        path = os.path.join(HERE, "samples", name)
        out, ok = run_capture(path, workdir)
        passed = ok and "\nOK" in out and "[exit 0]" in out
        if not passed and name in AI_SCRIPTS and ("onnxruntime" in out or "onnx" in out):
            SKIPPED.append(name)  # 环境没装后端，不算代码问题
            print("\n=== %s ===\nSKIP（缺推理后端）" % name)
            continue
        results.append((name, passed))
        print("\n=== %s ===\n%s" % (name, out.strip()[:800]))

    # pygame：无显示器时用 dummy 驱动，跑 5 秒不崩视为通过
    path = os.path.join(HERE, "samples", GUI_SCRIPT)
    env = os.environ.copy()
    env.setdefault("SDL_VIDEODRIVER", "dummy")
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    try:
        proc = subprocess.Popen([python_exe(), "-u", path], cwd=workdir, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(5)
        alive = proc.poll() is None
        proc.terminate()
        try:
            tail = proc.communicate(timeout=3)[0] or ""
        except Exception:  # noqa: BLE001
            tail = ""
        results.append((GUI_SCRIPT, alive))
        print("\n=== %s ===\n存活5秒=%s %s" % (GUI_SCRIPT, alive, tail.strip()[:400]))
    except Exception as exc:  # noqa: BLE001
        results.append((GUI_SCRIPT, False))
        print("\n=== %s ===\n! 无法启动: %r" % (GUI_SCRIPT, exc))

    print("\n" + "=" * 40)
    for name, ok in results:
        print("%-22s %s" % (name, "PASS" if ok else "FAIL"))
    for name in SKIPPED:
        print("%-22s %s" % (name, "SKIP（缺 onnxruntime）"))
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
