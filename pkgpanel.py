"""Quick Install 面板（V3）：只从白名单里选，不开放自由输入。

三档用颜色区分：纯 Python（绿）/ 已验证 wheel（蓝）/ 实验（红，点下去也会先警告）。
点 Install 时走 packages.install()，输出实时回输出面板，不另起控制台。
"""
from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup

import packages

TIER_COLOR = {
    packages.PURE: (0.35, 0.75, 0.45, 1),
    packages.VERIFIED: (0.45, 0.65, 0.95, 1),
    packages.DANGER: (0.9, 0.45, 0.35, 1),
}


class PackageRow(BoxLayout):
    """kv 里引用；字段由 PackagePanel 填"""

    name = StringProperty("")
    why = StringProperty("")
    tier = StringProperty("")
    tier_color = ListProperty([0.6, 0.6, 0.6, 1])
    note = StringProperty("")


class PackagePanel(BoxLayout):
    query = StringProperty("")
    rows = ListProperty([])
    status = StringProperty("")

    def __init__(self, on_install=None, say=print, **kw):
        super().__init__(**kw)
        self.on_install = on_install or (lambda *_: None)
        self.say = say or (lambda *_: None)
        self.refresh()

    def refresh(self):
        rows = []
        for p in packages.search(self.query):
            rows.append({
                "name": p["name"],
                "why": "%s｜%s" % (packages.TIER_LABEL[p["tier"]], p.get("why", "")),
                "tier": p["tier"],
                "tier_color": list(TIER_COLOR[p["tier"]]),
                "note": p.get("note") or p.get("evidence", ""),
            })
        self.rows = rows
        self.status = "%d 个包" % len(rows)

    def pick(self, name):
        p = packages.get(name)
        if not p:
            return
        if p["tier"] == packages.DANGER:
            self.say("! %s 是实验档：%s\n  替代方案：%s\n"
                     % (name, p.get("evidence", ""), p.get("alt", "先在 PC 上做")))
        self.say("$ %s\n" % packages.install_cmd(name))
        self.on_install(name)


class PackagePopup(Popup):
    """工具条「📦」弹出的面板"""

    def __init__(self, on_install=None, say=print, **kw):
        kw.setdefault("title", "Quick Install（白名单）")
        kw.setdefault("size_hint", (0.95, 0.85))
        super().__init__(**kw)
        self.content = PackagePanel(on_install=on_install, say=say)
