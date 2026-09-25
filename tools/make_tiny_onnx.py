"""生成一个迷你 ONNX 分类模型，用于自检（不需要 torch、不联网、几 KB）。

结构：输入 images[1,3,H,W] -> ReduceMean(空间维度) -> Gemm -> logits[1,3]
用途：在没有真实模型时，验证 ai_runtime 的加载/预处理/推理/topk 整条通路。
"""
import argparse
import os
import sys

import numpy as np


def build(path="tiny_cls.onnx", opset=13):
    from onnx import TensorProto, helper, numpy_helper

    X = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 224, 224])
    Y = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, 3])

    # opset13 里 ReduceMean 的 axes 已是属性而非输入，用 GlobalAveragePool 更稳
    pooled = helper.make_tensor_value_info("pooled", TensorProto.FLOAT, [1, 3])

    W = numpy_helper.from_array(
        np.array([[1.0, -0.5, 0.2], [0.3, 1.0, -0.7], [-0.4, 0.6, 1.0]], dtype=np.float32), "W")
    B = numpy_helper.from_array(np.array([0.1, 0.0, -0.1], dtype=np.float32), "B")

    shape = numpy_helper.from_array(np.array([1, 3], dtype=np.int64), "rshape")

    nodes = [
        helper.make_node("GlobalAveragePool", ["images"], ["gap"]),
        helper.make_node("Reshape", ["gap", "rshape"], ["pooled"]),
        helper.make_node("Gemm", ["pooled", "W", "B"], ["logits"]),
    ]
    graph = helper.make_graph(nodes, "tiny_cls", [X], [Y], initializer=[W, B, shape])
    graph.value_info.append(pooled)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", opset)])
    model.ir_version = 8
    try:
        import onnx
        onnx.checker.check_model(model)
    except Exception as exc:  # noqa: BLE001
        print("! checker 跳过：%s" % exc)
    with open(path, "wb") as fh:
        fh.write(model.SerializeToString())
    return os.path.abspath(path)


def build_text(path="tiny_txt.onnx", seq=8, nclass=3, opset=13):
    """迷你文本模型：ids[1,seq] int64 -> Cast -> Gemm -> logits[1,nclass]"""
    from onnx import TensorProto, helper, numpy_helper

    X = helper.make_tensor_value_info("ids", TensorProto.INT64, [1, seq])
    Y = helper.make_tensor_value_info("logits", TensorProto.FLOAT, [1, nclass])
    W = numpy_helper.from_array(np.random.rand(seq, nclass).astype(np.float32) - 0.5, "W")
    B = numpy_helper.from_array(np.zeros(nclass, dtype=np.float32), "B")
    nodes = [
        helper.make_node("Cast", ["ids"], ["ids_f"], to=TensorProto.FLOAT),
        helper.make_node("Gemm", ["ids_f", "W", "B"], ["logits"]),
    ]
    graph = helper.make_graph(nodes, "tiny_txt", [X], [Y], initializer=[W, B])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", opset)])
    model.ir_version = 8
    with open(path, "wb") as fh:
        fh.write(model.SerializeToString())
    return os.path.abspath(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="tiny_cls.onnx")
    ap.add_argument("--text", action="store_true", help="生成文本模型（ids[1,8] int64）")
    args = ap.parse_args()
    p = build_text(args.out) if args.text else build(args.out)
    print("生成：%s（%.1f KB）" % (p, os.path.getsize(p) / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
