"""设备能力探测（V4）：电量 / ABI / 内存 / 后台限制。

全部走「读得到就读，读不到就说读不到」，不假设 root、不硬编 sudo/apt，
也不假装在没有 Android API 的环境里能拿到电量。

数据源（都不需要 root）：
  电量    /sys/class/power_supply/*/capacity      （Android 与 Linux 通用）
          plyer.battery（APK 里若打包了 plyer 更准）
  ABI     platform.machine() / os.uname().machine
  内存    /proc/meminfo 的 MemTotal
  CPU 数  os.cpu_count()（注意：Android 常返回全部核心数，不代表能用几个）
"""
from __future__ import annotations

import os

try:
    import platform
except Exception:  # noqa: BLE001
    platform = None


# ---------------------------------------------------------------- 电量
def battery_percent():
    """返回 0-100 的电量；读不到返回 None（不要返回 0，那是"没电"的意思）。"""
    # 先试 plyer：APK 里打进去的话它走的是 Android BatteryManager，最准
    try:
        from plyer import battery  # noqa: PLC0415

        st = battery.status
        pct = (st or {}).get("percentage")
        if pct is not None:
            return int(pct)
    except Exception:  # noqa: BLE001
        pass

    base = "/sys/class/power_supply"
    try:
        for name in sorted(os.listdir(base)):
            cap = os.path.join(base, name, "capacity")
            if os.path.isfile(cap):
                with open(cap, encoding="utf-8") as fh:
                    v = int(fh.read().strip())
                if 0 <= v <= 100:
                    return v
    except Exception:  # noqa: BLE001
        pass
    return None


def is_charging():
    """是否在充电；读不到返回 None"""
    try:
        from plyer import battery  # noqa: PLC0415

        st = battery.status or {}
        if "isCharging" in st:
            return bool(st["isCharging"])
    except Exception:  # noqa: BLE001
        pass
    base = "/sys/class/power_supply"
    try:
        for name in sorted(os.listdir(base)):
            st = os.path.join(base, name, "status")
            if os.path.isfile(st):
                with open(st, encoding="utf-8") as fh:
                    return fh.read().strip().lower() in ("charging", "full")
    except Exception:  # noqa: BLE001
        pass
    return None


def power_budget(pct=None):
    """按电量给出节流建议。

    返回 (档位, 建议文本)。电量读不到时给 'unknown'，按常规处理，别当没电。
    """
    if pct is None:
        return "unknown", "读不到电量：按常规模式运行（不主动降频）"
    if pct <= 15:
        return "low", "电量 ≤15%：别跑长任务，先落盘进度；关闭实时输出刷新"
    if pct <= 40:
        return "mid", "电量 ≤40%：长任务请分块执行并落盘，避免被打断后重跑"
    return "good", "电量充足：可以跑长任务，但仍建议进度落盘"


# ---------------------------------------------------------------- ABI / CPU
def abi():
    """返回主 ABI 线索：'arm64' / 'armv7' / 'x86_64' 等，读不到返回 ''"""
    m = ""
    try:
        m = (platform.machine() if platform else "") or ""
    except Exception:  # noqa: BLE001
        pass
    if not m:
        try:
            m = os.uname().machine
        except Exception:  # noqa: BLE001
            m = ""
    m = (m or "").lower()
    if m in ("aarch64", "arm64", "armv8l"):
        return "arm64"
    if m.startswith("armv7") or m == "armv7l":
        return "armv7"
    return m


def is_android() -> bool:
    import sys

    return hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ


def cpu_count() -> int:
    try:
        return os.cpu_count() or 1
    except Exception:  # noqa: BLE001
        return 1


def total_mem_mb():
    """总内存 MB；读不到返回 None"""
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    return int(line.split()[1]) // 1024
    except Exception:  # noqa: BLE001
        pass
    return None


def suggest_threads(mem_mb=None, cpus=None):
    """端侧推理建议线程数。

    手机上别盲目开多核：小模型 batch=1 时多核收益极小，还更费电、更容易触发温控降频。
    """
    cpus = cpus or cpu_count()
    if mem_mb is not None and mem_mb <= 1024:
        return 1
    if is_android():
        return 1 if cpus <= 4 else 2
    return max(1, min(4, cpus))


# ---------------------------------------------------------------- 汇总
def report() -> dict:
    pct = battery_percent()
    mem = total_mem_mb()
    return {
        "android": is_android(),
        "abi": abi(),
        "cpus": cpu_count(),
        "mem_total_mb": mem,
        "battery_percent": pct,
        "charging": is_charging(),
        "power_budget": power_budget(pct)[0],
        "suggest_threads": suggest_threads(mem),
    }


def report_text() -> str:
    r = report()
    tier, advice = power_budget(r["battery_percent"])
    lines = [
        "设备能力：",
        "  Android      : %s" % r["android"],
        "  ABI          : %s" % (r["abi"] or "(未知)"),
        "  CPU 数        : %d" % r["cpus"],
        "  总内存        : %s" % ("%d MB" % r["mem_total_mb"] if r["mem_total_mb"] else "(读不到)"),
        "  电量          : %s（充电中=%s）" % (
            "%d%%" % r["battery_percent"] if r["battery_percent"] is not None else "(读不到)",
            r["charging"]),
        "  推理建议线程  : %d" % r["suggest_threads"],
        "  电量档位      : %s —— %s" % (tier, advice),
    ]
    return "\n".join(lines)
