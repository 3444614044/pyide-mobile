"""MVP 运行器：子进程跑 .py，流式回传 stdout+stderr。

设计要点（为 Android 端侧准备）：
- 不 import 用户脚本，一律 subprocess 隔离：脚本崩溃不会拖死 IDE。
- 流式读取 + 行缓冲：手机上能实时看到 print。
- 停止用 terminate->kill 两级，避免子进程变孤儿。
"""
import os
import shutil
import subprocess
import sys
import threading

MAX_LINES = 4000  # 输出面板保留上限，防内存爆


def python_exe() -> str:
    """找到能用的解释器。

    Pydroid / p4a 打包后 sys.executable 未必指向真实文件，
    因此做 exists 校验后再回退到 PATH 上的 python3/python。
    """
    exe = getattr(sys, "executable", "") or ""
    if exe and os.path.exists(exe):
        return exe
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return found
    return exe or "python3"


class ScriptRunner:
    def __init__(self, on_line, on_state):
        """
        on_line(text): 追加一段输出（子线程调用，调用方需自行切主线程）
        on_state(running: bool): 运行状态变化
        """
        self.on_line = on_line
        self.on_state = on_state
        self.proc = None
        self._thread = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def run(self, path: str, cwd: str = None):
        if self.running:
            self.on_line("! 已有任务在运行，先点「停止」\n")
            return
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            self.on_line("! 文件不存在：%s\n" % path)
            return
        cwd = cwd or os.path.dirname(path) or "."
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        exe = python_exe()
        try:
            self.proc = subprocess.Popen(
                [exe, "-u", path],
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                errors="replace",
            )
        except Exception as exc:  # noqa: BLE001 - 要把原因原样喂给输出面板
            self.on_line("! 启动失败：%r\n" % (exc,))
            self.on_line("  解释器：%s\n" % exe)
            self.on_line("  建议：换解释器路径，或确认该脚本未占用 stdin\n")
            return
        self.on_line("$ cd %s\n$ %s -u %s\n%s\n" % (cwd, os.path.basename(exe), path, "-" * 30))
        self.on_state(True)
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self):
        proc = self.proc
        try:
            for line in proc.stdout:
                self.on_line(line)
        except Exception as exc:  # noqa: BLE001
            self.on_line("! 读取输出失败：%r\n" % (exc,))
        finally:
            try:
                rc = proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()
                rc = proc.wait()
            self.proc = None
            self.on_line("\n[exit %d]\n" % rc)
            self.on_state(False)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            threading.Timer(2.0, self._force_kill).start()

    def _force_kill(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.kill()
            except Exception:  # noqa: BLE001
                pass
