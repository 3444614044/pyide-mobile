"""文件树控件：只扫应用私有目录，不申请存储权限，不碰 /system。

展示逻辑在 ui.kv，扫描逻辑复用 workspace.list_dir（纯函数，可无头测）。
"""
from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from workspace import list_dir


class FileTree(BoxLayout):
    path = StringProperty("")
    entries = ListProperty([])

    def on_path(self, *_):
        self.refresh()

    def refresh(self):
        self.entries = list_dir(self.path)
