"""PyIDE Mobile — MVP：文件树 / 编辑器 / 输出面板 + 运行 .py

桌面调试：  python main.py
手机上跑：  Pydroid 3 打开本文件，或 buildozer 打包成 APK

这一层只干两件事：显示（kv/控件）和转发（把按钮事件丢给 workspace.Workspace）。
真正的读写与子进程运行都在 workspace.py，方便无头测试。
"""
import os
from collections import deque

from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput

from codearea import CodeArea  # noqa: F401  (kv 里通过类名引用)
from filetree import FileTree  # noqa: F401  (kv 里通过类名引用)
import diag
from pkgpanel import PackagePanel, PackagePopup  # noqa: F401  (kv 里通过类名引用)
import packages
from runner import MAX_LINES
from workspace import Workspace

APP_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = '''# 新建文件模板：print 会实时出现在下方输出面板
import os, sys

print("python:", sys.version.split()[0])
print("cwd   :", os.getcwd())
'''


def _mono_available() -> bool:
    try:
        from kivy import kivy_data_dir
        return os.path.exists(os.path.join(kivy_data_dir, "fonts", "RobotoMono-Regular.ttf"))
    except Exception:  # noqa: BLE001
        return False


class RootUI(BoxLayout):
    pass


class PyIDEApp(App):
    root_path = StringProperty("")
    out_text = StringProperty("")
    font_size = NumericProperty(14)
    has_mono = BooleanProperty(True)

    def build(self):
        self.title = "PyIDE Mobile"
        # 没有等宽字体就退回 Roboto，避免 font_name 找不到导致启动失败
        self.has_mono = _mono_available()
        # Android 上软键盘弹起时把编辑区顶上去（无头环境会失败，忽略即可）
        self._setup_window()

        self._buf = deque(maxlen=MAX_LINES)
        self._dirty = False
        self._run_buf = []        # 本次运行的输出，结束后交给错误解释器
        self._capturing = False
        self.current_path = None

        self.root_path = os.path.join(self.user_data_dir, "projects")
        self.ws = Workspace(self.root_path, say=self._say)
        self.ws.seed_samples(os.path.join(APP_DIR, "samples"))
        self.ws.on_start = self._on_run_start
        self.ws.on_finish = self._on_run_finish
        os.makedirs(os.path.join(self.root_path, "models"), exist_ok=True)  # 放模型

        # kv 里是类规则，load_file 只注册规则；实例化 RootUI 时才套用
        Builder.load_file(os.path.join(APP_DIR, "ui.kv"))
        self.ui = RootUI()
        Clock.schedule_interval(self._flush, 0.15)
        self._say("就绪。左侧选 .py，编辑后点「运行」。\n")
        return self.ui

    def _setup_window(self) -> bool:
        try:
            from kivy.core.window import Window  # 延迟导入：无头环境 import 本模块也不炸

            Window.softinput_mode = "pan"
            Window.bind(on_keyboard=self._on_key)
            return True
        except Exception:  # noqa: BLE001 - 无头/无 window 环境
            return False

    # ---------------- 输出面板 ----------------
    def _say(self, text):
        self._buf.append(text)
        if self._capturing:
            self._run_buf.append(text)
        self._dirty = True

    # ---------------- 运行结束：自动挂诊断建议 ----------------
    def _on_run_start(self):
        self._run_buf = []
        self._capturing = True

    def _on_run_finish(self):
        self._capturing = False
        Clock.schedule_once(lambda *_: self._diagnose(), 0.05)

    def _diagnose(self):
        text = "".join(self._run_buf[-200:])   # 只看最后 200 行，别扫全历史
        self._run_buf = []
        advice = diag.explain(text)
        if advice:
            self._say("\n" + diag.format(advice, markup=True))

    def _flush(self, *_):
        if not self._dirty:
            return
        self._dirty = False
        self.out_text = "".join(self._buf)
        if self.ui is not None and "outsv" in self.ui.ids:
            self.ui.ids.outsv.scroll_y = 0  # 自动滚到底

    # ---------------- 文件操作 ----------------
    def entry_clicked(self, path, kind):
        if kind in ("dir", "up"):
            self.ui.ids.tree.path = path
            return
        if not path.lower().endswith(".py"):
            ext = os.path.splitext(path)[1].lower()
            if ext in (".onnx", ".pt", ".ptl", ".pte", ".tflite", ".pth"):
                self._say(
                    "%s 是模型文件，不能直接编辑。用法：\n"
                    "  import ai_runtime\n"
                    "  m = ai_runtime.load('%s')\n"
                    "  m.predict_image(img, topk=3)\n" % (os.path.basename(path), path))
            else:
                self._say("! 只能编辑 .py（%s）\n" % os.path.basename(path))
            return
        try:
            self.ui.ids.code.text = self.ws.open_file(path)
        except Exception as exc:  # noqa: BLE001
            self._say("! 打开失败：%r\n" % (exc,))
            return
        self.current_path = path
        self.ui.ids.fname.text = os.path.basename(path)
        self._say("打开 %s\n" % path)

    def do_new(self):
        name = (self.ui.ids.fname.text or "").strip()
        if not name:
            name = self.ws.next_name(self.ui.ids.tree.path)
        if not name.endswith(".py"):
            name += ".py"
        self.current_path = os.path.join(self.ui.ids.tree.path, name)
        self.ui.ids.code.text = TEMPLATE
        self.ui.ids.fname.text = name
        self.do_save()

    def do_save(self, *_):
        name = (self.ui.ids.fname.text or "").strip()
        if not name:
            self._say("! 先填文件名\n")
            return False
        if not name.endswith(".py"):
            name += ".py"
        current = getattr(self, "current_path", None)
        target = current if current and os.path.basename(current) == name \
            else os.path.join(self.ui.ids.tree.path, name)
        try:
            self.ws.save(target, self.ui.ids.code.text)
        except Exception as exc:  # noqa: BLE001
            self._say("! 保存失败：%r\n" % (exc,))
            return False
        self.current_path = target
        self.ui.ids.tree.refresh()
        return True

    def do_delete(self):
        path = getattr(self, "current_path", None)
        if not path or not os.path.isfile(path):
            self._say("! 没有选中文件\n")
            return
        try:
            self.ws.delete(path)
        except Exception as exc:  # noqa: BLE001
            self._say("! 删除失败：%r\n" % (exc,))
            return
        self.current_path = None
        self.ui.ids.code.text = ""
        self.ui.ids.fname.text = ""
        self.ui.ids.tree.refresh()

    # ---------------- Quick Install（V3）----------------
    def do_packages(self):
        PackagePopup(on_install=self._install_package, say=self._say).open()

    def pick_package(self, name):
        self._say("$ %s\n" % packages.install_cmd(name))
        self._install_package(name)

    def _install_package(self, name):
        def work():
            rc = packages.install(name, on_line=self._say)
            self._say("[pip exit %d]\n" % rc)

        import threading
        threading.Thread(target=work, daemon=True).start()

    def do_refresh(self):
        self.ui.ids.tree.refresh()
        self._say("已刷新\n")

    def zoom(self, step):
        self.font_size = max(10, min(24, self.font_size + step))

    # ---------------- 运行 ----------------
    def do_run(self):
        if not self.do_save():
            return
        self.ws.run(self.current_path)

    def do_stop(self):
        self.ws.stop()

    # ---------------- 返回键 ----------------
    def _on_key(self, _win, key, *_args):
        if key == 27:  # Android 返回 / ESC
            tree = self.ui.ids.tree
            if tree.path and tree.path != self.root_path:
                tree.path = os.path.dirname(tree.path)
                return True
            if self.ws.running:
                self.do_stop()
                return True
        return False


if __name__ == "__main__":
    PyIDEApp().run()
