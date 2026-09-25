"""Quick Install 白名单（V3）

手机上装包和 PC 不是一回事：ABI 是 arm64/aarch64，没有编译栈，包体每 MB 都是真金白银。
所以这里不做"随便 pip install"，只给三档：

  pure       纯 Python，无 C 扩展 —— 装上就能用
  verified   官方有 aarch64 / manylinux_aarch64 wheel —— 能装，注意体积
  danger     实验档：装得上也可能跑不动或撑爆内存 —— 默认提示"建议 PC 训练/预处理"

判定依据写进每条的 `evidence` 字段，别靠记忆拍脑袋；新增条目必须填。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

PURE = "pure"
VERIFIED = "verified"
DANGER = "danger"

TIER_LABEL = {
    PURE: "纯 Python（推荐）",
    VERIFIED: "已验证 ARM wheel",
    DANGER: "实验 / 建议 PC 训练",
}

#: name -> 白名单条目
#:  p4a: buildozer requirements 里对应的 recipe（None 表示只能运行时 pip，别打进 APK）
PACKAGES = [
    # ---------------- 纯 Python ----------------
    dict(name="pygments", tier=PURE, why="编辑器语法高亮", p4a="pygments",
         evidence="纯 Python，无 C 扩展"),
    dict(name="markdown", tier=PURE, why="写文档/笔记", p4a="markdown",
         evidence="纯 Python"),
    dict(name="tabulate", tier=PURE, why="终端打印小表格", p4a="tabulate",
         evidence="纯 Python"),
    dict(name="python-dateutil", tier=PURE, why="日期解析", p4a="python-dateutil",
         evidence="纯 Python（six 依赖同为纯 Python）"),
    dict(name="attrs", tier=PURE, why="数据类/配置对象", p4a="attrs",
         evidence="纯 Python"),
    dict(name="tomli", tier=PURE, why="读 pyproject.toml", p4a="tomli",
         evidence="纯 Python"),
    dict(name="rich", tier=PURE, why="终端富文本（Pydroid 里好看）", p4a=None,
         evidence="纯 Python，依赖 markdown-it-py / mdurl / pygments 均为纯 Python"),

    # ---------------- 已验证 ARM wheel ----------------
    dict(name="numpy", tier=VERIFIED, why="数组计算，示例已依赖", p4a="numpy",
         evidence="PyPI 有 manylinux_aarch64 wheel；p4a 有 recipe（已进 MVP 打包）"),
    dict(name="Pillow", tier=VERIFIED, why="图像处理，端侧输入预处理必备", p4a="Pillow",
         evidence="官方 aarch64 wheel；p4a 有 recipe"),
    dict(name="onnxruntime", tier=VERIFIED, why="AI 运行器默认后端", p4a=None,
         evidence="官方发布 aarch64 wheel；打进 APK 需 p4a recipe（预编译 .so），纯 pip 装不进去",
         note="APK 场景请走 .ptl/.pte 的 Java 路线，或自备 recipe"),
    dict(name="regex", tier=VERIFIED, why="比 re 更强的正则", p4a="regex",
         evidence="有 aarch64 wheel"),
    dict(name="pyyaml", tier=VERIFIED, why="配置文件", p4a="pyyaml",
         evidence="aarch64 wheel 可用（libyaml 为可选 C 扩展）"),
    dict(name="scipy", tier=VERIFIED, why="科学计算（体积偏大）", p4a=None,
         evidence="有 aarch64 wheel，但 ~40MB，手机上谨慎"),
    dict(name="pandas", tier=VERIFIED, why="表格分析（体积偏大）", p4a=None,
         evidence="有 aarch64 wheel，依赖 numpy+时区数据，冷启动变慢"),

    # ---------------- 实验 / 建议 PC ----------------
    dict(name="torch", tier=DANGER, why="大模型训练/完整 torch",
         alt="先在 PC 上 torch.onnx.export 导出 .onnx，手机只做推理",
         evidence="CPU wheel 本体 ~200MB+，手机上装得下也不该装",
         note="只建议 Pydroid 里装 CPU 版做小模型 eval；别打进 APK"),
    dict(name="tensorflow", tier=DANGER, why="TF 训练/推理",
         alt="端侧用 tflite-runtime（体积 ~2MB）",
         evidence="完整 TF 包体数百 MB，手机上不可用"),
    dict(name="opencv-python", tier=DANGER, why="OpenCV",
         alt="opencv-python-headless（去掉 GUI 依赖）",
         evidence="完整版带 GUI 依赖，手机上易编/装失败"),
    dict(name="matplotlib", tier=DANGER, why="绘图",
         alt="在 PC 上出图存 PNG，手机只做展示",
         evidence="字体与后端依赖多，手机端体验差、包体大"),
    dict(name="scikit-learn", tier=DANGER, why="传统 ML 训练",
         alt="PC 上训练 -> 导出 onnx，手机只推理",
         evidence="依赖 scipy，体积与内存都不适合手机"),
    dict(name="transformers", tier=DANGER, why="大模型推理",
         alt="PC 导出 onnx + int8 量化，手机用 ai_runtime 加载",
         evidence="依赖重、冷启动慢，手机端只适合极小模型"),
    dict(name="ultralytics", tier=DANGER, why="YOLO 训练",
         alt="PC 训练 -> export format=onnx -> 手机推理",
         evidence="训练需要显存与算力，手机做不到"),
]

_BY_NAME = {p["name"].lower(): p for p in PACKAGES}


def get(name: str):
    return _BY_NAME.get((name or "").lower())


def by_tier(tier: str):
    return [p for p in PACKAGES if p["tier"] == tier]


def search(q: str):
    q = (q or "").strip().lower()
    if not q:
        return list(PACKAGES)
    return [p for p in PACKAGES if q in p["name"].lower() or q in p.get("why", "").lower()]


def tier_of(name: str) -> str:
    p = get(name)
    return p["tier"] if p else "unknown"


# ---------------------------------------------------------------- 安装
def pip_available() -> bool:
    """APK 里默认没有 pip（除非打包进去）；Pydroid / 桌面一般都有。"""
    for probe in (["python3", "-m", "pip", "--version"],
                  [sys.executable or "python3", "-m", "pip", "--version"]):
        try:
            return subprocess.run(probe, capture_output=True, timeout=20).returncode == 0
        except Exception:  # noqa: BLE001
            continue
    return shutil.which("pip") is not None


def install_cmd(name: str) -> str:
    """给出可复制的安装命令。纯 Python 走源码包，其余强制二进制 wheel（不现场编译）。"""
    p = get(name)
    if p and p["tier"] == PURE:
        return "pip install %s" % name
    # --only-binary=:all: 手机上不允许现场 gcc 编译，直接失败比卡 20 分钟好
    return "pip install %s --only-binary=:all: --no-compile" % name


def install(name: str, on_line, timeout=300) -> int:
    """执行安装，流式回传输出。返回退出码。

    注意：APK 里通常没有 pip，会明确提示换 buildozer requirements —— 不硬编 sudo/apt。
    """
    p = get(name)
    if p and p["tier"] == DANGER:
        on_line("! %s 属实验档：%s\n" % (name, p.get("evidence", "")))
        if p.get("alt"):
            on_line("  建议：%s\n" % p["alt"])
        on_line("  仍要继续的话，装完大概率也很慢/很占内存。\n")
    if not pip_available():
        on_line("! 当前环境没有 pip（APK 默认不带）。\n")
        on_line("  改用打包：把 %s 写进 buildozer.spec 的 requirements\n" % (p["p4a"] if p and p["p4a"] else name))
        on_line("  或先在 Pydroid 3 / 桌面上验证。\n")
        return 127
    exe = sys.executable or "python3"
    args = [exe, "-m", "pip", "install", "--disable-pip-version-check"]
    args += [] if (p and p["tier"] == PURE) else ["--only-binary=:all:"]
    args += ["--no-compile", name]
    on_line("$ %s\n" % " ".join(os.path.basename(a) if a == exe else a for a in args))
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, errors="replace")
    except Exception as exc:  # noqa: BLE001
        on_line("! 启动 pip 失败：%r\n" % (exc,))
        return 127
    for line in proc.stdout:
        on_line(line)
    return proc.wait()


def spec_requirements(names) -> str:
    """把选中的包转成 buildozer 的 requirements 字符串；返回 (字符串, 被跳过的包列表)"""
    keep, skipped = ["python3", "kivy"], []
    for n in names:
        p = get(n)
        if not p:
            skipped.append((n, "不在白名单，先确认有没有 aarch64 wheel 与 p4a recipe"))
            continue
        if not p.get("p4a"):
            skipped.append((n, p.get("note") or "无 p4a recipe，只能运行时装"))
            continue
        if p["tier"] == DANGER:
            skipped.append((n, "实验档，不建议打进 APK：" + (p.get("alt") or "")))
            continue
        if p["p4a"] not in keep:
            keep.append(p["p4a"])
    return ",".join(keep), skipped
