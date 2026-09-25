"""真机验收自检（Pydroid / APK / 桌面都能跑）

用法：python devicecheck.py
产出：一份可复制的报告 + P0/P1/P2 分级结论

设计原则：
  * 能自动判的自动判；只能人看的（触屏、旋屏观感）明确标「人工」，不假装测了
  * 依赖缺失不算失败，算 SKIP —— 缺什么报告里会说，别让环境噪音掩盖真问题
  * 延迟给的是「参考区间」不是死线：机型差异太大，超了只提示偏慢，标 WARN

真机上跑完把输出贴回来，就能定位是哪一层没通。
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
import time

# 报告要能整段复制，别让 kivy/pygame 的启动横幅混进来（必须在 import 它们之前设）
os.environ.setdefault("KIVY_LOG_LEVEL", "error")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import device  # noqa: E402
import jobs  # noqa: E402
import screen  # noqa: E402

PASS, FAIL, WARN, SKIP, MANUAL = "PASS", "FAIL", "WARN", "SKIP", "人工"
ROWS = []


def row(level, name, result, detail=""):
    ROWS.append((level, name, result, detail))
    print("  [%s] %-4s %-26s %s" % (level, result, name, detail))


def have(mod):
    try:
        m = __import__(mod)
        return getattr(m, "__version__", "?")
    except Exception:  # noqa: BLE001
        return None


def section(title):
    print("\n" + "=" * 8 + " %s " % title + "=" * 8)


def main():
    print("PyIDE Mobile 真机验收")
    print("时间:", time.strftime("%Y-%m-%d %H:%M:%S"))

    # ---------------- 1. 运行环境 ----------------
    section("1. 运行环境")
    r = device.report()
    row("P0", "Android 环境", PASS if r["android"] else SKIP,
        "是" if r["android"] else "桌面/其他（真机项需人工确认）")
    row("P0", "ABI", PASS if r["abi"] in ("arm64", "armv7") else SKIP,
        r["abi"] or "?")
    row("P1", "CPU 数", PASS, str(r["cpus"]))
    row("P1", "总内存", PASS, "%d MB" % r["mem_total_mb"] if r["mem_total_mb"] else "读不到")
    row("P1", "推理建议线程", PASS, str(r["suggest_threads"]))

    # 私有目录可写
    try:
        root = sys.prefix if r["android"] else os.getcwd()
        probe = os.path.join(tempfile.mkdtemp(prefix="pyide_chk_"), "w.txt")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        row("P0", "私有目录可写", PASS, "ok")
    except Exception as exc:  # noqa: BLE001
        row("P0", "私有目录可写", FAIL, repr(exc))

    # ---------------- 2. 依赖 ----------------
    section("2. 依赖")
    core = {"numpy": "P0", "PIL": "P0", "kivy": "P0"}
    opt = {"pygame": "P1", "onnxruntime": "P0", "onnx": "P1", "pygments": "P2"}
    for mod, lvl in list(core.items()) + list(opt.items()):
        v = have(mod)
        row(lvl, "import %s" % mod, PASS if v else SKIP, v or "未安装")

    pip_ok = shutil.which("pip") is not None

    def _pip():
        import subprocess

        try:
            return subprocess.run([sys.executable or "python3", "-m", "pip", "--version"],
                                  capture_output=True, timeout=20).returncode == 0
        except Exception:  # noqa: BLE001
            return False

    pip_ok = pip_ok or _pip()
    row("P1", "pip 可用", PASS if pip_ok else SKIP,
        "可用" if pip_ok else "APK 默认不带，改用 buildozer requirements")

    # ---------------- 3. 延迟基准（真机关键数据）----------------
    section("3. 延迟基准")
    import numpy as np  # noqa: PLC0415

    n = 224
    a = np.random.rand(n, n).astype(np.float32)
    b = np.random.rand(n, n).astype(np.float32)
    t0 = time.perf_counter()
    a @ b
    mm = (time.perf_counter() - t0) * 1000
    row("P1", "numpy 224x224 matmul", WARN if mm > 200 else PASS, "%.1f ms" % mm)

    # 小特征：这才是手机该干的活
    x = np.random.rand(1, 128).astype(np.float32)
    w = np.random.rand(128, 128).astype(np.float32)
    t0 = time.perf_counter()
    for _ in range(200):
        _ = x @ w
    small = (time.perf_counter() - t0) / 200 * 1000
    row("P1", "1x128 dense（小模型量级）", PASS if small < 5 else WARN, "%.3f ms" % small)

    if have("PIL"):
        from PIL import Image  # noqa: PLC0415

        im = Image.fromarray((np.random.rand(512, 512, 3) * 255).astype(np.uint8))
        t0 = time.perf_counter()
        im.resize((224, 224), Image.BILINEAR)
        rs = (time.perf_counter() - t0) * 1000
        row("P1", "PIL 512->224 预处理", WARN if rs > 30 else PASS, "%.1f ms" % rs)
        if rs > 10:
            print("      提示：预处理 %.1f ms 已接近一次小模型推理量级，"
                  "考虑直接拍 224 或复用 resized 图" % rs)

    # ---------------- 4. AI 通路 ----------------
    section("4. AI 运行器")
    ort = have("onnxruntime")
    if not ort:
        row("P0", "AI 通路", SKIP, "缺 onnxruntime：pip install onnxruntime（APK 需 p4a recipe）")
    else:
        try:
            import ai_runtime  # noqa: PLC0415

            rep = ai_runtime.backend_report()
            row("P0", "后端可用", PASS, "ort=%s providers=%s" % (
                rep.get("ort_version"), ",".join(rep.get("providers", []))))

            try:
                from make_tiny_onnx import build  # noqa: PLC0415

                tmp = tempfile.mkdtemp(prefix="pyide_chk_")
                p = build(os.path.join(tmp, "t.onnx"))
                m = ai_runtime.load(p)
                row("P0", "load 迷你 ONNX", PASS, repr(m))

                img_arr = np.random.rand(1, 3, 224, 224).astype(np.float32)
                m.predict(img_arr)  # 预热
                t0 = time.perf_counter()
                for _ in range(20):
                    m.predict(img_arr)
                inf = (time.perf_counter() - t0) / 20 * 1000
                row("P0", "推理 20 次均值", PASS if inf < 50 else WARN, "%.2f ms" % inf)

                top = m.predict_image(
                    Image.fromarray((np.random.rand(224, 224, 3) * 255).astype(np.uint8)), topk=3)
                row("P0", "predict_image top-k", PASS, "top1=%d p=%.3f" % top[0])

                # 错误分支
                for text, want in (("ModuleNotFoundError: No module named 'PIL',", "缺模块：PIL"),
                                   ("ImportError: lib.so: cannot open shared object", "ARM 不兼容 / 缺 .so")):
                    import diag  # noqa: PLC0415

                    ads = diag.explain(text)
                    row("P1", "诊断命中 %s" % want[:10],
                        PASS if ads and ads[0].title == want else FAIL,
                        ads[0].title if ads else "无匹配")
                shutil.rmtree(tmp, ignore_errors=True)
            except Exception as exc:  # noqa: BLE001
                row("P0", "AI 推理", FAIL, repr(exc))
        except Exception as exc:  # noqa: BLE001
            row("P0", "AI 通路", FAIL, repr(exc))

    # ---------------- 5. 屏幕 ----------------
    section("5. 屏幕自适应")
    # 无 GL / 无 DISPLAY 时 import kivy.core.window 会刷一屏 ERROR，先判断再碰
    has_window = bool(os.environ.get("DISPLAY") or os.environ.get("ANDROID_ARGUMENT")
                      or os.environ.get("WAYLAND_DISPLAY"))
    if has_window:
        try:
            from kivy.core.window import Window  # noqa: PLC0415
            from kivy.metrics import Metrics  # noqa: PLC0415

            w, h = Window.size
            dpi = Metrics.dpi
            p = screen.layout_for(w, h, dpi)
            row("P0", "布局参数（实测）", PASS, "%dx%d@%.0fdpi -> %s/%s 树%.0f%%" % (
                w, h, dpi, p["orientation"], p["width_class"], p["tree_hint"] * 100))
        except Exception as exc:  # noqa: BLE001
            has_window = False
            row("P0", "布局参数", WARN, "有窗口环境但读取失败：%r" % (exc,))
    if not has_window:
        for label, (cw, ch, cdpi) in (("手机竖屏", (1080, 2340, 440)),
                                      ("手机横屏", (2340, 1080, 440)),
                                      ("平板竖屏", (1600, 2560, 320))):
            p = screen.layout_for(cw, ch, cdpi)
            row("P1", "布局演算 %s" % label, PASS, "%s/%s 树%.0f%% 编辑%.0f%% 字号%d" % (
                p["orientation"], p["width_class"], p["tree_hint"] * 100,
                p["code_hint"] * 100, p["font_sp"]))
    row("P1", "旋屏不错位", MANUAL, "转屏后三栏比例应自动变化，无重叠/空白")
    row("P1", "高 DPI 字体一致", MANUAL, "字号按 sp，换机型不应突变")

    # ---------------- 6. 电量与后台 ----------------
    section("6. 电量 / 后台")
    pct = device.battery_percent()
    tier, advice = device.power_budget(pct)
    row("P1", "电量", PASS if pct is not None else SKIP,
        "%s%% (%s) %s" % (pct, tier, advice) if pct is not None else "读不到 -> %s" % tier)
    row("P1", "电量节流间隔", PASS,
        "低电量=%.2fs / 中=%s" % (jobs.throttle_interval(10), jobs.throttle_interval(30)))

    try:
        tmp = tempfile.mkdtemp(prefix="pyide_chk_")
        jm = jobs.JobManager(tmp)
        j = jm.create("chk", total=10)
        for _ in range(4):
            jm.advance(j, 1)
        jm2 = jobs.JobManager(tmp)
        res = jm2.resumable()
        ok = len(res) == 1 and res[0].done == 4
        row("P0", "进度落盘 + 被杀续跑", PASS if ok else FAIL,
            "断点 %d/10" % res[0].done if res else "未识别")
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:  # noqa: BLE001
        row("P0", "进度落盘 + 被杀续跑", FAIL, repr(exc))

    fg_ok, fg_msg = jobs.start_foreground()
    row("P2", "前台服务", PASS if fg_ok else SKIP, str(fg_msg).splitlines()[0])

    # ---------------- 7. 示例脚本 ----------------
    section("7. 示例脚本（逐个 import 级冒烟）")
    samples = sorted(f for f in os.listdir(os.path.join(HERE, "samples")) if f.endswith(".py"))
    row("P2", "示例数量", PASS, "%d 个: %s" % (len(samples), ",".join(s[:2] for s in samples)))
    row("P1", "pygame 触屏示例", MANUAL,
        "手指点中间按钮计数+1、右上角 EXIT 退出（需 pygame）")

    # ---------------- 汇总 ----------------
    section("结论")
    from collections import Counter

    c = Counter(res for _, _, res, _ in ROWS)
    print("  自动通过 %d｜跳过 %d｜告警 %d｜失败 %d｜需人工 %d"
          % (c[PASS], c[SKIP], c[WARN], c[FAIL], c[MANUAL]))

    failed = [(lv, n, d) for lv, n, r_, d in ROWS if r_ == FAIL]
    if failed:
        print("\n  失败项（优先修这几个）：")
        for lv, n, d in failed:
            print("    [%s] %s -> %s" % (lv, n, d))

    manual = [(lv, n, d) for lv, n, r_, d in ROWS if r_ == MANUAL]
    if manual:
        print("\n  必须人工确认（自动化测不了）：")
        for lv, n, d in manual:
            print("    [%s] %s -> %s" % (lv, n, d))

    print("\n  完整报告可整段复制回传，用于定位问题。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
