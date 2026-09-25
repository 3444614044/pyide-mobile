"""设备能力 + 后台续跑演示（V4）

跑一下看四件事：
  1. 电量与节流档位（读不到就如实说读不到，不编数字）
  2. ABI / CPU / 内存 / 建议推理线程数
  3. 长任务分块推进 + 进度落盘
  4. 模拟"被杀"：只写到一半就退出，下次启动能从断点续跑
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import device  # noqa: E402
import jobs  # noqa: E402


def demo_device():
    print("== 设备能力 ==")
    print(device.report_text())
    r = device.report()
    print("  块间间隔    : %.2fs（电量节流）"
          % jobs.throttle_interval(r["battery_percent"]))


def demo_layout():
    print("\n== 布局自适应（纯计算，不依赖窗口） ==")
    import screen
    cases = [
        ("小屏手机竖屏", 720, 1280, 320),
        ("常规手机竖屏", 1080, 2340, 440),
        ("手机横屏", 2340, 1080, 440),
        ("平板竖屏", 1600, 2560, 320),
    ]
    for name, w, h, dpi in cases:
        p = screen.layout_for(w, h, dpi)
        print("  %-12s %s/%s 树%.0f%% 编辑%.0f%% 字号%d"
              % (name, p["orientation"], p["width_class"],
                 p["tree_hint"] * 100, p["code_hint"] * 100, p["font_sp"]))


def demo_jobs():
    print("\n== 后台任务：进度落盘 ==")
    root = os.path.join(os.getcwd(), "_v4demo")
    jm = jobs.JobManager(root)
    job = jm.create("demo_count", total=20)
    print("  新建:", job)
    for i in range(12):          # 故意只跑一半就"被杀"
        jm.advance(job, 1)
    print("  跑到一半：", job, "（进度 %.0f%%）" % (job.progress * 100))

    print("\n== 模拟进程被杀后重启 ==")
    jm2 = jobs.JobManager(root)   # 换一个实例，等于新进程
    resumable = jm2.resumable()
    print("  未完成任务数：", len(resumable))
    for j in resumable:
        print(" ", jm2.resume_hint(j).replace("\n", "\n  "))

    j3 = jm2.load("demo_count")
    for i in range(j3.done, j3.total):
        jm2.advance(j3, 1)
    jm2.finish(j3)
    print("  续跑完成：", j3)
    print("  剩余未完成：", len(jm2.resumable()))

    print("\n== 分块推进（让出 CPU） ==")
    for a, b in jobs.chunked_range(0, 20, chunk=5, sleep_s=0.01):
        print("   chunk %d-%d" % (a, b))

    print("\n== 前台服务 ==")
    ok, msg = jobs.start_foreground()
    print("  可用：%s" % ok)
    for line in str(msg).splitlines():
        print("  ", line)

    import shutil
    shutil.rmtree(root, ignore_errors=True)


def main():
    demo_device()
    demo_layout()
    demo_jobs()
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
