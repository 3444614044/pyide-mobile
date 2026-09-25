"""一键跑全部自检：uitest(逻辑+kv) / v3test(白名单+诊断) / aitest(AI) / selftest(示例)

用法：python alltest.py
退出码：全过 0，任一失败 1。手机上（Pydroid）也能直接跑，用来验收整包。
"""
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ["uitest.py", "v3test.py", "v4test.py", "aitest.py", "selftest.py"]


def main():
    results = []
    for name in SUITES:
        print("\n" + "=" * 20 + " %s " % name + "=" * 20)
        try:
            proc = subprocess.run([sys.executable or "python3", "-u", name],
                                  cwd=HERE, capture_output=True, text=True, timeout=600)
            out = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            proc, out = None, "! 超时 600s"
        lines = out.splitlines()
        # 只打印 PASS/FAIL/SKIP 汇总行，细节回原 suite 看
        keep = [l for l in lines if ("PASS" in l or "FAIL" in l or "SKIP" in l or l.startswith("FAILS"))]
        print("\n".join(keep[-14:]))
        rc = proc.returncode if proc else 1
        results.append((name, rc))

    print("\n" + "=" * 52)
    for name, rc in results:
        print("%-14s %s" % (name, "OK" if rc == 0 else "FAILED"))
    return 0 if all(rc == 0 for _, rc in results) else 1


if __name__ == "__main__":
    sys.exit(main())
