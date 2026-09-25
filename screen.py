"""屏幕自适应（V4）：横竖屏 / DPI / 断点布局。

手机上最容易被忽略的三件事：
  1. 旋屏后布局错位 —— 因为写了死像素
  2. 高低 DPI 字体大小不一 —— 因为用了 px 而不是 sp/dp
  3. 折叠屏/平板宽度完全不同 —— 因为只按一种宽度设计

这里把「给一个宽高，返回该用什么布局」做成纯函数，能无头测。
kv 里只负责按返回值摆放，不自己算。
"""
from __future__ import annotations

KIVY_MDPI = 160.0  # Kivy 的 dp 基准：160dpi 时 1dp = 1px


def orientation(width: float, height: float) -> str:
    # 正方形归竖屏：多数 App 在 1:1（如分屏、某些折叠形态）下按竖屏布局更稳
    return "landscape" if width > height else "portrait"


def width_class(width_dp: float) -> str:
    """按 dp 宽度分档（不是像素，换 DPI 的机器才不会跳档）"""
    if width_dp < 360:
        return "compact"     # 小屏手机竖屏
    if width_dp < 600:
        return "phone"       # 常规手机竖屏
    if width_dp < 840:
        return "wide"        # 大屏手机横屏 / 小平板
    return "tablet"          # 平板 / 折叠屏展开


def layout_for(width_px: float, height_px: float, dpi: float = KIVY_MDPI):
    """给像素宽高 + dpi，返回布局参数。

    返回字段：
      orientation  竖/横
      width_class  宽度档位
      tree_hint    文件树占宽比例（横屏时收窄，把地方给编辑器）
      code_hint    编辑器占高比例
      font_sp      建议字号（dp 里的 sp）
      columns      1 = 单栏（文件树收起），2 = 双栏
    """
    scale = (dpi or KIVY_MDPI) / KIVY_MDPI
    w_dp = width_px / scale if scale else width_px
    h_dp = height_px / scale if scale else height_px
    ori = orientation(width_px, height_px)
    wc = width_class(w_dp)

    if ori == "landscape":
        # 横屏：竖向空间紧张，编辑器让一点给输出；文件树收窄到 22%
        return dict(orientation=ori, width_class=wc, tree_hint=0.22, code_hint=0.55,
                    font_sp=13, columns=2, note="横屏：输出面板加高，方便看 traceback")
    if wc == "compact":
        # 小屏竖屏：文件树太占地方，收到 26%
        return dict(orientation=ori, width_class=wc, tree_hint=0.26, code_hint=0.62,
                    font_sp=13, columns=2, note="小屏：文件树收窄")
    if wc == "tablet":
        # 平板/折叠屏：文件树可以大方一点，字号也可以大写
        return dict(orientation=ori, width_class=wc, tree_hint=0.28, code_hint=0.66,
                    font_sp=16, columns=2, note="平板：三栏拉开，字号放大")
    return dict(orientation=ori, width_class=wc, tree_hint=0.32, code_hint=0.62,
                font_sp=14, columns=2, note="常规手机竖屏")


def apply_to_tree(tree, params):
    """把布局参数套到文件树控件上（宽度比例）"""
    if tree is not None:
        tree.size_hint_x = params["tree_hint"]


def apply_to_split(code_widget, out_widget, params):
    """把布局参数套到编辑器/输出的高度比例上"""
    if code_widget is not None:
        code_widget.size_hint_y = params["code_hint"]
    if out_widget is not None:
        out_widget.size_hint_y = 1.0 - params["code_hint"]
