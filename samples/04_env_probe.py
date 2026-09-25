"""环境体检：只打印，不写任何敏感路径，无 root 也能跑。

后面 V2 选推理后端（PyTorch Mobile / ExecuTorch / ONNX Runtime / TFLite）
之前，先看这几个值：ABI(arm64-v8a / armeabi-v7a)、内存上限、可写目录。
"""
import os
import platform
import sys

print("executable :", sys.executable or "(empty)")
print("version    :", sys.version.split()[0])
print("machine    :", platform.machine(), "| ABI 线索:", platform.architecture()[0])
print("cwd        :", os.getcwd())
print("writable   :", os.access(os.getcwd(), os.W_OK))

# 手机内存上限（Android 可读 /proc/meminfo；桌面同样可读）
try:
    with open("/proc/meminfo", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("MemTotal"):
                print("MemTotal   :", line.split(":", 1)[1].strip())
                break
except Exception as exc:  # noqa: BLE001
    print("MemTotal   : 读不到（%s）" % type(exc).__name__)

probe = os.path.join(os.getcwd(), "_probe.txt")
try:
    with open(probe, "w", encoding="utf-8") as fh:
        fh.write("ok")
    with open(probe, encoding="utf-8") as fh:
        print("io         :", fh.read())
finally:
    if os.path.exists(probe):
        os.remove(probe)

print("OK")
