"""后台长任务（V4）：进度落盘 + 被杀续跑 + 前台服务说明。

现实约束（先说清楚，别硬来）：
  * Android 会杀后台进程，Python 侧无法阻止 —— 唯一正解是「进度落盘，重启后续跑」。
  * 前台服务能把进程优先级提上去，但需要 Java 层 + FOREGROUND_SERVICE 权限，
    Python 侧（无 pyjnius / 无自定义 Java 源码）做不到。本模块提供：
      - start_foreground()：有 pyjnius 就真起，没有就明确告知要加什么，不静默失败。
  * 不常驻高 CPU：任务分块执行，块之间 sleep，电量低时自动加大间隔。

用法：
    from jobs import JobManager
    jm = JobManager(app_dir)
    job = jm.create("train", total=100)
    for i, item in enumerate(items):
        do(item)
        jm.advance(job, 1)          # 每步落盘（可配 every）
    jm.finish(job)

    # 下次启动：
    for job in jm.resumable():      # 未完成的，可续跑
        ...
"""
from __future__ import annotations

import json
import os
import threading
import time

STATE_VERSION = 1


def _now() -> float:
    return time.time()


class Job:
    def __init__(self, data: dict):
        self.data = data

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def done(self) -> int:
        return int(self.data.get("done", 0))

    @property
    def total(self) -> int:
        return int(self.data.get("total", 0))

    @property
    def status(self) -> str:
        return self.data.get("status", "new")

    @property
    def progress(self) -> float:
        return (self.done / self.total) if self.total else 0.0

    def __repr__(self):
        return "<Job %s %d/%d %s>" % (self.id, self.done, self.total, self.status)


class JobManager:
    """进度落盘到 <root>/jobs/<id>.json，进程被杀后靠它续跑。"""

    def __init__(self, root: str, say=print, save_every=1):
        self.dir = os.path.join(root, "jobs")
        os.makedirs(self.dir, exist_ok=True)
        self.say = say or (lambda *_: None)
        self.save_every = max(1, int(save_every))
        self._lock = threading.Lock()
        self._n = 0

    # ---------------- 生命周期 ----------------
    def create(self, job_id: str, total: int, meta=None) -> Job:
        path = self._path(job_id)
        if os.path.isfile(path):
            return self.load(job_id)          # 已存在就接着用，不覆盖
        data = {"v": STATE_VERSION, "id": job_id, "total": int(total), "done": 0,
                "status": "running", "meta": meta or {},
                "created": _now(), "updated": _now()}
        self._write(data)
        return Job(data)

    def load(self, job_id: str) -> Job:
        with open(self._path(job_id), encoding="utf-8") as fh:
            return Job(json.load(fh))

    def _path(self, job_id: str) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_id)
        return os.path.join(self.dir, safe + ".json")

    def _write(self, data: dict):
        data["updated"] = _now()
        tmp = self._path(data["id"]) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, self._path(data["id"]))   # 原子写：被杀也不会留下半个文件

    def advance(self, job: Job, step: int = 1, note=None):
        with self._lock:
            job.data["done"] = min(job.total, job.done + step)
            if note:
                job.data.setdefault("notes", []).append(note)
            self._n += 1
            if self._n % self.save_every == 0:
                self._write(job.data)

    def set_meta(self, job: Job, **kv):
        job.data.setdefault("meta", {}).update(kv)
        self._write(job.data)

    def finish(self, job: Job):
        job.data["status"] = "done"
        self._write(job.data)
        self.say("[任务完成] %s\n" % job.id)

    def abort(self, job: Job, why="user"):
        job.data["status"] = "aborted"
        job.data["why"] = why
        self._write(job.data)

    # ---------------- 续跑 ----------------
    def resumable(self):
        """返回所有未完成的任务（status=running 但进度没走完，或上次是被杀的）"""
        out = []
        for name in sorted(os.listdir(self.dir)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.dir, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:  # noqa: BLE001
                continue
            if data.get("status") == "running":
                out.append(Job(data))
        return out

    def resume_hint(self, job: Job) -> str:
        return ("发现未完成任务 %s：%d/%d（%.0f%%）。\n"
                "  续跑：jm.load('%s') 然后从 done=%d 继续，别从 0 开始。"
                % (job.id, job.done, job.total, job.progress * 100, job.id, job.done))

    def drop(self, job_id: str):
        p = self._path(job_id)
        if os.path.isfile(p):
            os.remove(p)


# ---------------------------------------------------------------- 节流
def chunked_range(start: int, total: int, chunk: int, sleep_s: float = 0.0,
                  should_pause=None):
    """分块推进：每块之间让出 CPU，必要时暂停。

    手机上「一直 100% CPU 跑」会触发温控降频，还更容易被系统判定为异常后台。
    should_pause() 返回 True 时暂停（比如电量低或用户切到后台）。
    """
    i = start
    while i < total:
        end = min(total, i + chunk)
        yield i, end
        i = end
        if i >= total:
            break
        if should_pause and should_pause():
            return
        if sleep_s > 0:
            time.sleep(sleep_s)


def throttle_interval(battery_pct=None) -> float:
    """按电量给出块间间隔（秒）：电量低就慢一点，别硬扛。"""
    if battery_pct is None:
        return 0.0
    if battery_pct <= 15:
        return 0.5
    if battery_pct <= 40:
        return 0.15
    return 0.0


# ---------------------------------------------------------------- 前台服务
def start_foreground(title="PyIDE", text="任务运行中"):
    """尝试起前台服务。做不到就明确说要补什么，不静默失败。

    需要两样东西（缺一不可）：
      1. buildozer.spec 里 android.permissions 加 FOREGROUND_SERVICE（Android 14 起还要
         细分类型，如 FOREGROUND_SERVICE_DATA_SYNC）
      2. requirements 加 pyjnius（p4a 有 recipe），或自己用 android.add_src 挂 Java 源码
    """
    try:
        from jnius import autoclass, cast  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return (False, "没有 pyjnius，起不了前台服务。需要：\n"
                       "  1) buildozer.spec: android.permissions = FOREGROUND_SERVICE\n"
                       "  2) requirements 加 pyjnius\n"
                       "做不到也别慌 —— 进度落盘（JobManager）已经保证被杀后可续跑。")
    try:
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        Intent = autoclass("android.content.Intent")
        ctx = activity.getApplicationContext()
        intent = Intent(ctx, autoclass("%s.Service" % activity.getClass().getName().split("$")[0]))
        intent.setPackage(ctx.getPackageName())
        ctx.startForegroundService(intent)
        return True, "已请求前台服务（%s / %s）" % (title, text)
    except Exception as exc:  # noqa: BLE001
        return False, ("请求前台服务失败：%r\n"
                       "常见原因：权限没声明、Android 版本要求细分类型、或没有 Service 实现。" % (exc,))
