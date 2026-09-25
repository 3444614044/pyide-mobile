"""int8 动态量化：把 fp32 ONNX 压到 1/4 体积，ARM CPU 上通常快 2-3 倍。

在 PC 上跑（手机上不装 onnxruntime 的训练/量化工具链）：
    python tools/quantize_onnx.py model.onnx --out model_int8.onnx
    python tools/quantize_onnx.py model.onnx --check        # 只体检，不落地

注意：动态量化只量化 MatMul/Conv 的权重，激活保持 fp32 —— 小模型够用，
精度掉了再考虑静态量化（需要校准集，脚本不提供）。
"""
import argparse
import os
import sys

REDUCE = """
量化后如果精度掉太多：
  1. 先看是不是 per-channel 的问题：加 --per-channel 重新量化
  2. 还不行就退回 fp32，改小模型或裁剪通道 —— 手机上别指望静态量化的那点收益
  3. 别在手机上跑量化（工具链 + 算力都不划算）
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--out", default=None)
    ap.add_argument("--per-channel", action="store_true", help="按通道量化，精度更好、速度略慢")
    ap.add_argument("--check", action="store_true", help="只打印体检信息")
    args = ap.parse_args()

    if not os.path.isfile(args.model):
        print("! 找不到模型：%s" % args.model)
        return 2
    size_mb = os.path.getsize(args.model) / 1e6
    print("输入：%s（%.1f MB）" % (args.model, size_mb))

    try:
        import onnx
    except Exception:  # noqa: BLE001
        print("! 缺 onnx：pip install onnx")
        return 2

    try:
        m = onnx.load(args.model)
        ins = [(i.name, [d.dim_param or d.dim_value for d in i.type.tensor_type.shape.dim])
               for i in m.graph.input]
        outs = [o.name for o in m.graph.output]
        ops = sorted({n.op_type for n in m.graph.node})
        print("  输入：%s" % ins)
        print("  输出：%s" % outs)
        print("  算子：%s" % ", ".join(ops))
        print("  opset：%s" % [o.version for o in m.opset_import])
    except Exception as exc:  # noqa: BLE001
        print("! 解析 ONNX 失败：%r" % (exc,))
        return 2

    if args.check:
        return 0

    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic
    except Exception:  # noqa: BLE001
        print("! 缺量化工具：pip install onnxruntime (>=1.14)")
        return 2

    out = args.out or os.path.splitext(args.model)[0] + "_int8.onnx"
    try:
        quantize_dynamic(
            model_input=args.model,
            model_output=out,
            weight_type=QuantType.QInt8,
            per_channel=args.per_channel,
            reduce_range=True,   # ARM CPU 上更稳，避免某些后端饱和
        )
    except Exception as exc:  # noqa: BLE001
        print("! 量化失败：%r" % (exc,))
        print(REDUCE)
        return 2

    old, new = os.path.getsize(args.model), os.path.getsize(out)
    print("输出：%s（%.1f MB -> %.1f MB，%.0f%%）" % (out, old / 1e6, new / 1e6, new / old * 100))
    print(REDUCE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
