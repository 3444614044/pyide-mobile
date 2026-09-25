"""错误解释器 + Quick Install 白名单演示（V3）

跑一下就知道这两个功能长什么样：
  1. 故意 import 一个不存在的模块，让 diag 把它翻译成可执行的下一步
  2. 打印白名单三档，以及选中一批包后该往 buildozer.spec 里写什么

真机（Pydroid / APK）里，这部分已经内建在 IDE 中：
  运行报错后输出面板自动追加「诊断建议」，工具条「📦」打开安装面板。
"""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import diag  # noqa: E402
import packages  # noqa: E402


def demo_diag():
    print("== 1. 报错 -> 建议 ==")
    try:
        import definitely_missing_mod_xyz  # noqa: F401
    except Exception:  # noqa: BLE001
        tb = traceback.format_exc()
        print("原始 traceback 最后一行：")
        print(" ", tb.strip().splitlines()[-1])
        print("\n诊断输出：")
        print(diag.explain_text(tb, markup=False))

    print("== 2. 四类典型报错 ==")
    samples = [
        "ImportError: libtorch_cpu.so: cannot open shared object file",
        "Fatal signal 4 (SIGILL), code 1",
        "onnxruntime.capi InvalidGraph: opset not supported",
        "PermissionError: [Errno 13] Permission denied: '/system/lib'",
    ]
    for text in samples:
        ads = diag.explain(text)
        head = ads[0] if ads else None
        print("  %-52s -> %s" % (text[:52], head.title if head else "(未匹配)"))


def demo_packages():
    print("\n== 3. Quick Install 白名单 ==")
    for tier in (packages.PURE, packages.VERIFIED, packages.DANGER):
        names = ", ".join(p["name"] for p in packages.by_tier(tier))
        print("  %-18s %s" % (packages.TIER_LABEL[tier], names))

    print("\n== 4. 选包 -> buildozer requirements ==")
    picked = ["pygments", "numpy", "Pillow", "torch", "onnxruntime"]
    req, skipped = packages.spec_requirements(picked)
    print("  requirements = %s" % req)
    for name, why in skipped:
        print("  跳过 %-12s %s" % (name, why))

    print("\n== 5. 安装命令示例 ==")
    for name in ("pygments", "numpy", "torch"):
        print("  %-10s %s" % (name, packages.install_cmd(name)))
    print("  pip 是否可用：%s" % packages.pip_available())


def main():
    demo_diag()
    demo_packages()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
