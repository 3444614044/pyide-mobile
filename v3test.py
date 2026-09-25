"""V3 自检：Quick Install 白名单 + 错误解释器。

用法：python v3test.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import diag  # noqa: E402
import packages  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print("%-34s %s %s" % (name, "PASS" if cond else "FAIL", extra))
    if not cond:
        FAILS.append(name)


# ---------------- 白名单 ----------------
check("白名单非空且三档齐全",
      all(packages.by_tier(t) for t in (packages.PURE, packages.VERIFIED, packages.DANGER)),
      "pure=%d verified=%d danger=%d" % tuple(
          len(packages.by_tier(t)) for t in ("pure", "verified", "danger")))

no_evidence = [p["name"] for p in packages.PACKAGES if not p.get("evidence")]
check("每条都有判定依据", not no_evidence, str(no_evidence))

no_alt = [p["name"] for p in packages.by_tier(packages.DANGER) if not p.get("alt")]
check("实验档都给了替代方案", not no_alt, str(no_alt))

check("未知包档位为 unknown", packages.tier_of("random_pkg_xyz") == "unknown")
check("numpy 属已验证档", packages.tier_of("numpy") == packages.VERIFIED)
check("torch 属实验档", packages.tier_of("torch") == packages.DANGER)
check("Pillow 有 p4a recipe", bool(packages.get("Pillow")["p4a"]))
check("onnxruntime 无 p4a recipe（诚实标注）", packages.get("onnxruntime")["p4a"] is None)

check("纯 Python 不强制二进制",
      packages.install_cmd("pygments") == "pip install pygments",
      packages.install_cmd("pygments"))
check("其余强制 --only-binary",
      "--only-binary=:all:" in packages.install_cmd("numpy"))

req, skipped = packages.spec_requirements(["numpy", "Pillow", "torch", "onnxruntime", "zzz"])
check("生成 buildozer requirements", req == "python3,kivy,numpy,Pillow", req)
check("torch/onnx/未知包被拦下", len(skipped) == 3, str([s[0] for s in skipped]))

# ---------------- 错误解释器 ----------------
cases = [
    ("ModuleNotFoundError: No module named 'PIL'", "缺模块：PIL", "Pillow"),
    ("ModuleNotFoundError: No module named 'numpy'", "缺模块：numpy", "numpy"),
    ("ModuleNotFoundError: No module named 'torch'", "缺模块：torch", "torch"),
    ("ImportError: libfoo.so: cannot open shared object file", "ARM 不兼容 / 缺 .so", None),
    ("Fatal signal 4 (SIGILL)", "ARM 不兼容", None),
    ("InvalidGraph: opset mismatch", "ONNX 算子/opset 不支持", None),
    ("Permission denied: /system/lib", "越权写入", None),
    ("MemoryError: Killed", "内存不足 / 模型过大", None),
    ("RuntimeError: load model.ptl failed", "模型格式/体积问题", None),
    ("ModuleNotFoundError: No module named 'matplotlib'", "缺模块：matplotlib", None),
]
for text, want_title, want_pkg in cases:
    ads = diag.explain(text)
    ok = bool(ads) and ads[0].title == want_title
    if ok and want_pkg:
        ok = ads[0].pkg == want_pkg
    check("解释：%s" % text[:40], ok,
          (ads[0].title if ads else "无匹配") + ((" pkg=" + ads[0].pkg) if ads and ads[0].pkg else ""))

check("空输入不报错", diag.explain("") == [] and diag.explain_text("") == "")
check("正常输出不给误报", diag.explain("hello world\nOK") == [],
      str([a.title for a in diag.explain("hello world\nOK")]))

fmt = diag.explain_text("ModuleNotFoundError: No module named 'PIL'", markup=False)
check("格式化含修复命令", "pip install Pillow" in fmt and "原因" in fmt)
mk = diag.explain_text("ModuleNotFoundError: No module named 'PIL'", markup=True)
check("markup 版本带颜色标签", "[color=" in mk)

check("未知模块也有建议",
      any(a.title.startswith("缺模块：weirdmod") for a in diag.explain(
          "ModuleNotFoundError: No module named 'weirdmod'")))

# ---------------- 集成：跑个报错脚本，诊断能接住 ----------------
import tempfile  # noqa: E402
import time  # noqa: E402

from workspace import Workspace  # noqa: E402

tmp = tempfile.mkdtemp(prefix="pyide_v3_")
lines = []
ws = Workspace(os.path.join(tmp, "projects"), say=lines.append)
ws.on_start = lambda: lines.clear()
bad = os.path.join(ws.root_path, "boom.py")
ws.save(bad, "import definitely_missing_mod_xyz\nprint('never')\n")
ws.run(bad)
deadline = time.time() + 30
while ws.running and time.time() < deadline:
    time.sleep(0.1)
out = "".join(lines)
ads = diag.explain(out)
check("报错脚本被诊断命中",
      bool(ads) and ads[0].title == "缺模块：definitely_missing_mod_xyz",
      (ads[0].title + " -> " + (ads[0].fix or "").splitlines()[0]) if ads else "无匹配")

# 正常脚本不该弹建议
ok_file = os.path.join(ws.root_path, "fine.py")
lines.clear()
ws.save(ok_file, "print('OK')\n")
ws.run(ok_file)
deadline = time.time() + 30
while ws.running and time.time() < deadline:
    time.sleep(0.1)
check("正常脚本不误报", diag.explain("".join(lines)) == [],
      str([a.title for a in diag.explain("".join(lines))]))

print("\n" + "=" * 48)
print("FAILS:", FAILS or "none")
sys.exit(1 if FAILS else 0)
