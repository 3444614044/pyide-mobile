"""把 .pt / torch 模型导出成手机能用的格式（在 PC 上跑，别在手机上跑）。

用法：
    python tools/export_pt.py --ckpt model.pt --out model.onnx --input-shape 1,3,224,224
    python tools/export_pt.py --ckpt model.pt --out model.ptl        # PyTorch Mobile lite
    python tools/export_pt.py --ckpt model.pt --int8                 # 顺手做动态量化

为什么在 PC：手机上没有完整 torch 编译栈，也不该为导出把 torch 打进 APK。
"""
import argparse
import os
import sys

EXPORT_USAGE = """\
导出后的格式该怎么用：
  .onnx -> Pydroid/桌面直接 import ai_runtime; 打进 APK 需要 p4a 的 onnxruntime recipe
  .ptl  -> Android 工程里用 Java：Module.load(assetFilePath(ctx, "model.ptl"))
  .pte  -> ExecuTorch Java/Kotlin 运行时（torch.export -> ExecuTorch）
"""


def load_module(ckpt):
    import torch
    try:
        obj = torch.load(ckpt, map_location="cpu", weights_only=False)
    except TypeError:
        obj = torch.load(ckpt, map_location="cpu")
    mod = obj if hasattr(obj, "forward") else (obj.get("model") or obj.get("net") or obj)
    if not hasattr(mod, "forward"):
        raise SystemExit("! .pt 里没有 nn.Module：存 'model'/'net' 键，或 torch.save(model, ...)")
    mod.eval()
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True, help="输入的 .pt 权重/整模型")
    ap.add_argument("--out", default="model.onnx", help=".onnx 或 .ptl")
    ap.add_argument("--input-shape", default="1,3,224,224")
    ap.add_argument("--opset", type=int, default=17, help="移动端建议 <=17")
    ap.add_argument("--int8", action="store_true", help="导出后做动态量化（仅 onnx）")
    args = ap.parse_args()

    try:
        import torch
    except Exception:  # noqa: BLE001
        print("! 这台机器没有 torch。请在 PC 上执行：")
        print("  pip install torch --index-url https://download.pytorch.org/whl/cpu")
        print(EXPORT_USAGE)
        return 2

    shape = tuple(int(x) for x in args.input_shape.split(","))
    mod = load_module(args.ckpt)
    dummy = torch.zeros(*shape)
    out = args.out
    ext = os.path.splitext(out)[1].lower()

    with torch.no_grad():
        if ext == ".onnx":
            torch.onnx.export(mod, dummy, out, input_names=["images"],
                              output_names=["logits"], opset_version=args.opset,
                              dynamic_axes={"images": {0: "batch"}})
            print("导出 ONNX：%s（%.1f MB）" % (out, os.path.getsize(out) / 1e6))
            if args.int8:
                here = os.path.dirname(os.path.abspath(__file__))
                q = os.path.join(here, "quantize_onnx.py")
                rc = os.system("%s %s --out %s" % (sys.executable, q, out))
                return rc >> 8
        elif ext == ".ptl":
            scripted = torch.jit.trace(mod, dummy) if not isinstance(mod, torch.jit.ScriptModule) else mod
            scripted = torch.jit.freeze(scripted)
            try:
                from torch.utils.mobile_optimizer import optimize_for_mobile
                scripted = optimize_for_mobile(scripted)
            except Exception as exc:  # noqa: BLE001
                print("! optimize_for_mobile 不可用（%s），输出未优化版" % exc)
            scripted._save_for_lite_interpreter(out)
            print("导出 lite：%s（%.1f MB）" % (out, os.path.getsize(out) / 1e6))
            print(EXPORT_USAGE)
        else:
            print("! 不认识的输出后缀 %s（只支持 .onnx / .ptl）" % ext)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
