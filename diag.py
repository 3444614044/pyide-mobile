"""错误解释器（V3）：把 traceback 翻译成"下一步该干嘛"。

新手在手机上看到 ModuleNotFoundError 就卡住了。这里不猜，只做规则匹配，
每条建议都带可执行命令，并且明确区分"缺 wheel / 模型过大 / ARM 不兼容 / 改用 ONNX"。

用法：
    import diag
    print(diag.format(explain(traceback_text)))
"""
from __future__ import annotations

import re

# 常见误报/噪声行，不参与匹配
_NOISE = re.compile(r"^\s*$|^\s*File \"|^\s*[a-z_]+\s*=|^\s*\^")

#: 模块 -> 建议（pip 名 / 说明 / 档位）
_MODULE_TIPS = {
    "numpy": ("numpy", "数组计算，示例与 AI 预处理都依赖它", "verified"),
    "PIL": ("Pillow", "图像处理；注意包名是 Pillow，不是 PIL", "verified"),
    "onnxruntime": ("onnxruntime", "AI 运行器默认后端", "verified"),
    "onnx": ("onnx", "模型导出与量化工具（PC 上用）", "pure"),
    "pygments": ("pygments", "编辑器语法高亮，缺了会自动退回原生输入框", "pure"),
    "torch": ("torch", "手机上别装完整 torch", "danger"),
    "tensorflow": ("tflite-runtime", "用 tflite-runtime 替代完整 TF", "danger"),
    "cv2": ("opencv-python-headless", "用 headless 版，去掉 GUI 依赖", "danger"),
    "matplotlib": ("-", "改为在 PC 出图存 PNG", "danger"),
    "sklearn": ("-", "PC 上训练后导出 onnx，手机只推理", "danger"),
    "scipy": ("scipy", "体积偏大，确认必要再装", "verified"),
    "pandas": ("pandas", "体积偏大，手机上谨慎", "verified"),
    "pygame": ("pygame", "仅示例/桌面调试；APK 需 p4a recipe，编不过就别加", "verified"),
    "requests": ("requests", "网络请求", "pure"),
    "yaml": ("pyyaml", "配置文件", "verified"),
}

# (正则, 标题, 原因, 修复)
_RULES = [
    (re.compile(r"ModuleNotFoundError: No module named '([^']+)'"),
     "缺模块", "这个包没装在当前环境里", None),

    (re.compile(r"ImportError: .*(cannot open shared object|undefined symbol|ELF)",
                re.I),
     "ARM 不兼容 / 缺 .so",
     "包装上了，但动态库对不上 ABI（arm64-v8a vs armeabi-v7a）或没编进 APK",
     "重装对应 aarch64 wheel：pip install <pkg> --only-binary=:all: --force-reinstall\n"
     "打进 APK 的话，这个包需要 p4a recipe，纯 pip 装不进去"),

    (re.compile(r"Illegal instruction|SIGILL|SIGSEGV|core dumped", re.I),
     "ARM 不兼容",
     "二进制里用了这台 CPU 不支持的指令（常见于 x86 编译产物或错误 ABI）",
     "确认 android.archs 包含 arm64-v8a；换官方 aarch64 wheel，别用源码包"),

    (re.compile(r"MemoryError|Killed|out of memory|oom", re.I),
     "内存不足 / 模型过大",
     "手机进程内存有硬上限（常见 128-512MB），大模型或小 batch 之外的用法都会踩",
     "把模型转 int8 动态量化（tools/quantize_onnx.py）；输入降到 224；batch 保持 1；\n"
     "还是不够就换更小的模型，别指望后台常驻大内存"),

    (re.compile(r"INVALID_GRAPH|opset|Unsupported operator|not supported.*operator", re.I),
     "ONNX 算子/opset 不支持",
     "导出时 opset 过高，或用了移动端后端没实现的算子",
     "PC 上重新导出：torch.onnx.export(..., opset_version=17, dynamo=False)\n"
     "仍不行就转 TFLite / .ptl"),

    (re.compile(r"Permission denied|Read-only file system|/system/", re.I),
     "越权写入",
     "无 root 不能写 /system、不能 sudo/apt，应用只能写自己的私有目录",
     "把路径换成 app.user_data_dir（本项目是 <私有目录>/projects）\n"
     "跨应用文件用 SAF（存储访问框架），不要硬写绝对路径"),

    (re.compile(r"No space left on device", re.I),
     "磁盘满了",
     "手机剩余空间不足以放下 wheel 或模型",
     "删掉 .buildozer 缓存与旧 APK；模型放私有目录并做 int8 量化"),

    (re.compile(r"No module named '?torch|torch.*not found", re.I),
     "缺 torch",
     "完整 torch 体积大，本项目的移动端路线不依赖它",
     "改用 ONNX：PC 上 torch.onnx.export 导出 .onnx，手机用 ai_runtime.load()\n"
     "或走 .ptl（PyTorch Mobile Java API）/ .pte（ExecuTorch）"),

    (re.compile(r"model.*(too large|过大)|\.ptl|\.pte", re.I),
     "模型格式/体积问题",
     ".ptl/.pte 在纯 Python 侧没有加载器；体积过大则冷启动会卡死",
     ".ptl -> Android 工程里 Module.load(assetFilePath(ctx, \"model.ptl\"))\n"
     ".pte -> ExecuTorch Java/Kotlin 运行时\n"
     "体积大 -> tools/quantize_onnx.py 做 int8 动态量化"),
]


class Advice:
    def __init__(self, title, why, fix=None, pkg=None, tier=None):
        self.title = title
        self.why = why
        self.fix = fix
        self.pkg = pkg
        self.tier = tier

    def __repr__(self):
        return "<Advice %s>" % self.title


def explain(text: str, limit=6):
    """traceback / 输出文本 -> [Advice]，按命中顺序去重返回。"""
    if not text:
        return []
    out, seen = [], set()

    def add(title, why, fix, pkg=None, tier=None):
        key = title
        if key in seen:
            return
        seen.add(key)
        out.append(Advice(title, why, fix, pkg, tier))

    for line in text.splitlines():
        if _NOISE.match(line):
            continue
        for pattern, title, why, fix in _RULES:
            m = pattern.search(line)
            if not m:
                continue
            if title == "缺模块":
                mod = m.group(1).split(".")[0]
                tip = _MODULE_TIPS.get(mod)
                if tip:
                    pkg, note, tier = tip
                    if pkg == "-":
                        add("缺模块：%s" % mod, note,
                            "这个包不建议在手机上装 —— %s" % note, tier=tier)
                    else:
                        add("缺模块：%s" % mod, note,
                            "pip install %s --only-binary=:all: --no-compile\n"
                            "（APK 里没 pip，就把它加进 buildozer.spec 的 requirements）" % pkg,
                            pkg=pkg, tier=tier)
                else:
                    add("缺模块：%s" % mod, "这个包不在白名单里",
                        "先确认有 aarch64 wheel 和 p4a recipe，再决定是否安装")
            else:
                add(title, why, fix)
        if len(out) >= limit:
            break
    return out


def format(advices, markup=True) -> str:
    """输出面板用的文本；markup=True 时给标题加 Kivy markup 颜色。"""
    if not advices:
        return ""
    lines = []
    if markup:
        lines.append("[color=ffcc66]── 诊断建议 ──[/color]")
    else:
        lines.append("── 诊断建议 ──")
    for a in advices:
        head = "• %s" % a.title
        lines.append("[color=99ddaa]%s[/color]" % head if markup else head)
        lines.append("  原因：%s" % a.why)
        if a.fix:
            for fl in str(a.fix).splitlines():
                lines.append("  → %s" % fl)
    return "\n".join(lines) + "\n"


def explain_text(text: str, markup=True) -> str:
    return format(explain(text), markup=markup)
