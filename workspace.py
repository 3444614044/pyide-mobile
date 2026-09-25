"""纯逻辑层：目录扫描 / 打开 / 保存 / 删除 / 运行。

刻意不 import 任何 Kivy widget —— 这样无头环境（CI、无 GL 服务器、手机后台脚本）
也能直接测。UI 层（main.py / ui.kv）只负责显示与转发，
V2 的 AI 运行器也会挂在这里，不碰 UI。
"""
import os
import shutil

from runner import ScriptRunner

SKIP_DIRS = {".git", "__pycache__", ".buildozer", "bin", ".gradle", ".idea"}
SHOW_EXT = (".py", ".txt", ".md", ".json", ".csv", ".png", ".jpg", ".jpeg")
MODEL_EXT = (".onnx", ".pt", ".ptl", ".pte", ".tflite", ".pth")


def list_dir(root):
    """列出目录 -> [{'kind','name','path'}]

    kind: 'up'(返回上级) / 'dir' / 'file'
    只走应用私有目录，不申请存储权限，不碰 /system。
    """
    items = []
    if not root or not os.path.isdir(root):
        return items
    parent = os.path.dirname(root)
    if parent and parent != root:
        items.append({"kind": "up", "name": "..", "path": parent})
    try:
        names = sorted(os.listdir(root))
    except Exception as exc:  # noqa: BLE001
        items.append({"kind": "err", "name": "读不了: %s" % exc, "path": root})
        return items
    dirs, files = [], []
    for name in names:
        full = os.path.join(root, name)
        if os.path.isdir(full):
            if name not in SKIP_DIRS and not name.startswith("."):
                dirs.append(name)
        elif os.path.isfile(full) and name.lower().endswith(SHOW_EXT + MODEL_EXT):
            files.append(name)
    items += [{"kind": "dir", "name": n + "/", "path": os.path.join(root, n)} for n in dirs]
    items += [{"kind": "file", "name": n, "path": os.path.join(root, n)} for n in files]
    return items


class Workspace:
    def __init__(self, root_path, say=print):
        self.root_path = root_path
        self.say = say or (lambda *_: None)
        self.current = None
        self.runner = ScriptRunner(on_line=self.say, on_state=self._on_state)

    def _on_state(self, running):
        self.say("[%s]\n" % ("运行中" if running else "结束"))

    @property
    def running(self):
        return self.runner.running

    # ---------- 初始化 ----------
    def seed_samples(self, samples_dir):
        os.makedirs(self.root_path, exist_ok=True)
        if os.path.isdir(samples_dir):
            for name in sorted(os.listdir(samples_dir)):
                if name.endswith(".py"):
                    dst = os.path.join(self.root_path, name)
                    if not os.path.exists(dst):
                        try:
                            shutil.copyfile(os.path.join(samples_dir, name), dst)
                        except Exception as exc:  # noqa: BLE001
                            self.say("! 复制示例失败 %s: %r\n" % (name, exc))
        return os.listdir(self.root_path)

    # ---------- 文件 ----------
    def open_file(self, path):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.current = path
        return text

    def save(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.current = path
        self.say("已保存 %s\n" % path)
        return path

    def delete(self, path):
        os.remove(path)
        if self.current == path:
            self.current = None
        self.say("已删除 %s\n" % path)

    def next_name(self, directory, prefix="new_"):
        i = 1
        while os.path.exists(os.path.join(directory, "%s%d.py" % (prefix, i))):
            i += 1
        return "%s%d.py" % (prefix, i)

    # ---------- 运行 ----------
    def run(self, path, cwd=None):
        self.runner.run(path, cwd=cwd or os.path.dirname(path))

    def stop(self):
        self.runner.stop()
