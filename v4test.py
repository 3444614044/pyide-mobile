"""V4 自检：屏幕自适应 / 设备探测 / 后台续跑。

用法：python v4test.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import device  # noqa: E402
import jobs  # noqa: E402
import screen  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print("%-32s %s %s" % (name, "PASS" if cond else "FAIL", extra))
    if not cond:
        FAILS.append(name)


# ---------------- 屏幕自适应 ----------------
check("竖屏判定", screen.orientation(1080, 2340) == "portrait")
check("横屏判定", screen.orientation(2340, 1080) == "landscape")
check("正方形归竖屏", screen.orientation(800, 800) == "portrait")

check("宽度档位 compact", screen.width_class(320) == "compact")
check("宽度档位 phone", screen.width_class(400) == "phone")
check("宽度档位 wide", screen.width_class(700) == "wide")
check("宽度档位 tablet", screen.width_class(900) == "tablet")

# 高 DPI 机器不能因为像素多就跳档：1080px@440dpi = 393dp（phone），别误判成 tablet
p = screen.layout_for(1080, 2340, 440)
check("按 dp 而非像素分档", p["width_class"] == "phone", "w_dp=%.0f" % (1080 / (440 / 160.0)))
q = screen.layout_for(1080, 2340, 160)
check("低 DPI 折算出更大 dp 宽度",
      q["width_class"] != p["width_class"] and screen.width_class(1080) == "tablet",
      "440dpi->%s / 160dpi->%s" % (p["width_class"], q["width_class"]))

land = screen.layout_for(2340, 1080, 440)
check("横屏收窄文件树", land["tree_hint"] < p["tree_hint"],
      "%.2f < %.2f" % (land["tree_hint"], p["tree_hint"]))
check("横屏加高输出面板", land["code_hint"] < p["code_hint"])

check("布局参数字段完整",
      all(k in p for k in ("orientation", "width_class", "tree_hint", "code_hint",
                           "font_sp", "columns", "note")))

# 所有分支都能返回，不抛异常
for w, h, d in ((320, 480, 120), (720, 1280, 320), (1080, 2340, 440),
                (2340, 1080, 440), (2560, 1600, 320), (1600, 2560, 320)):
    r = screen.layout_for(w, h, d)
    assert 0 < r["tree_hint"] < 1 and 0 < r["code_hint"] < 1, (w, h, d, r)
check("六种尺寸都不越界", True)

# ---------------- 设备探测 ----------------
r = device.report()
check("report 字段完整",
      all(k in r for k in ("android", "abi", "cpus", "mem_total_mb",
                           "battery_percent", "charging", "power_budget",
                           "suggest_threads")))
check("ABI 非空", r["abi"] != "", r["abi"])
check("CPU 数 >=1", r["cpus"] >= 1)
check("建议线程 >=1", r["suggest_threads"] >= 1, str(r["suggest_threads"]))
check("report_text 可打印", isinstance(device.report_text(), str) and "设备能力" in device.report_text())

pct = device.battery_percent()
check("电量要么读数要么 None", pct is None or (isinstance(pct, int) and 0 <= pct <= 100),
      str(pct))
tier, advice = device.power_budget(pct)
check("电量档位合法", tier in ("low", "mid", "good", "unknown"), tier)
check("低电量给节流建议", "落盘" in device.power_budget(10)[1], device.power_budget(10)[0])
check("满电不做降级", device.power_budget(90)[0] == "good")

check("线程建议随内存收缩", device.suggest_threads(mem_mb=512) == 1)
check("桌面多线程上限为 4", device.suggest_threads(mem_mb=8192, cpus=16) <= 4,
      str(device.suggest_threads(mem_mb=8192, cpus=16)))

check("节流间隔随电量增大",
      jobs.throttle_interval(10) > jobs.throttle_interval(30) >= jobs.throttle_interval(90),
      "%s %s %s" % (jobs.throttle_interval(10), jobs.throttle_interval(30),
                    jobs.throttle_interval(90)))

# ---------------- 后台任务 ----------------
tmp = tempfile.mkdtemp(prefix="pyide_v4_")
jm = jobs.JobManager(tmp)
job = jm.create("t1", total=10)
check("新建任务", job.status == "running" and job.total == 10, repr(job))
for _ in range(4):
    jm.advance(job, 1)
check("推进进度", job.done == 4 and abs(job.progress - 0.4) < 1e-9, "%.1f%%" % (job.progress * 100))

jm2 = jobs.JobManager(tmp)           # 模拟新进程
res = jm2.resumable()
check("识别未完成任务", len(res) == 1 and res[0].id == "t1", str([j.id for j in res]))
check("续跑提示含断点", "done=4" in jm2.resume_hint(res[0]))

j3 = jm2.load("t1")
for _ in range(j3.done, j3.total):
    jm2.advance(j3, 1)
jm2.finish(j3)
check("续跑到底", j3.done == 10 and j3.status == "done", repr(j3))
check("完成后不再可续", jm2.resumable() == [])

jm2.create("t2", total=3)
jm2.abort(jm2.load("t2"), why="test")
check("abort 后不可续", jm2.resumable() == [])

jm2.drop("t1")
check("drop 删除任务", jm2.resumable() == [] and not os.path.exists(jobs.JobManager(tmp)._path("t1")))

safe = jobs.JobManager(tmp)
weird = safe.create("a/b c*d", total=2)
check("任务 id 做文件名清洗", os.path.basename(safe._path("a/b c*d")).endswith(".json"), repr(weird.id))

chunks = list(jobs.chunked_range(0, 10, chunk=3))
check("分块覆盖完整区间", chunks[0][0] == 0 and chunks[-1][1] == 10, str(chunks))
check("分块不重叠不遗漏",
      all(chunks[i][1] == chunks[i + 1][0] for i in range(len(chunks) - 1)))
paused = list(jobs.chunked_range(0, 10, chunk=2, should_pause=lambda: True))
check("should_pause 能提前停", len(paused) == 1, str(paused))

ok, msg = jobs.start_foreground()
check("前台服务失败有明确指路",
      (ok is False) and ("FOREGROUND_SERVICE" in str(msg) or "pyjnius" in str(msg)),
      str(msg).splitlines()[0][:48])

shutil.rmtree(tmp, ignore_errors=True)
print("\n" + "=" * 46)
print("FAILS:", FAILS or "none")
sys.exit(1 if FAILS else 0)
