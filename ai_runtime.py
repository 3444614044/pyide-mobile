"""AI 运行器：把模型推理封装成三行代码。

    import ai_runtime
    m = ai_runtime.load("model.onnx")
    print(m.predict_image("cat.jpg", topk=3))

后端现实（别抱幻想，按层选）：
  a. 开发/教学（Pydroid 3 / Termux / 桌面）：pip 装 onnxruntime 或 CPU torch 的 ARM wheel，
     只做 batch=1 的小模型推理，不训练。
  b. 发布 APK：torch 的 .ptl 要走 PyTorch Mobile 的 Java API，.pte 走 ExecuTorch —— 这两条
     都是 Java/Kotlin 层的事，纯 Python 侧 import 不了，本模块会明确报错并指路。
  c. ONNX 在 APK 里能用，但需要 p4a recipe 把 onnxruntime 的 .so 编进去，不是 pip 一下就好。

性能红线：ARM CPU、batch=1、输入 <=224 或特征维度很小、默认 int8 动态量化。
"""
from __future__ import annotations

import os

import numpy as np

__all__ = ["load", "Model", "RuntimeUnavailable", "ModelTooLarge", "UnsupportedFormat",
           "backend_report", "IMAGENET_MEAN", "IMAGENET_STD"]

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# 手机上超过这个体积，冷启动和内存都会很难看（可按机型调）
SOFT_SIZE_LIMIT_MB = 60
HARD_SIZE_LIMIT_MB = 200


class RuntimeUnavailable(RuntimeError):
    """缺 wheel / 没 recipe / ABI 不对 —— 附具体安装建议"""


class ModelTooLarge(RuntimeError):
    """模型超出手机可接受体积"""


class UnsupportedFormat(RuntimeError):
    """格式本身需要别的层来加载（.ptl / .pte 走 Java）"""


# ---------------------------------------------------------------- 后端探测
def _try_import(name: str):
    try:
        return __import__(name)
    except Exception:  # noqa: BLE001 - ImportError 之外的 ABI/符号错误也要接住
        return None


def backend_report() -> dict:
    """体检：哪些后端在这台机器上真能用。写进输出面板，别猜。"""
    ort = _try_import("onnxruntime")
    torch = _try_import("torch")
    rep = {"onnxruntime": False, "torch": False, "abi": "", "providers": []}
    try:
        import platform
        rep["abi"] = platform.machine()
    except Exception:  # noqa: BLE001
        pass
    if ort is not None:
        rep["onnxruntime"] = True
        try:
            rep["providers"] = list(ort.get_available_providers())
            rep["ort_version"] = ort.__version__
        except Exception:  # noqa: BLE001
            pass
    if torch is not None:
        rep["torch"] = True
        rep["torch_version"] = getattr(torch, "__version__", "?")
    return rep


# ---------------------------------------------------------------- 预处理
def _to_nchw(src, input_size=224, normalize=True, mean=IMAGENET_MEAN, std=IMAGENET_STD):
    """PIL.Image / 路径 / ndarray -> (1,C,H,W) float32

    只在 predict_image 里用；特征类模型直接走 Model.predict(arr)。
    """
    from PIL import Image

    if isinstance(src, str):
        src = Image.open(src)
    if hasattr(src, "convert"):  # PIL
        im = src.convert("RGB")
        if input_size:
            im = im.resize((input_size, input_size), Image.BILINEAR)
        arr = np.asarray(im, dtype=np.float32) / 255.0
    else:
        arr = np.asarray(src, dtype=np.float32)
        if arr.max() > 1.5:  # 0..255 进来的，归一到 0..1
            arr = arr / 255.0
    if arr.ndim == 2:  # 灰度 -> 三通道
        arr = np.repeat(arr[..., None], 3, axis=-1)
    if arr.ndim == 3:
        arr = arr.transpose(2, 0, 1)  # HWC -> CHW
    arr = arr[None, ...]  # -> NCHW
    if normalize:
        m = np.asarray(mean, dtype=np.float32).reshape(1, -1, 1, 1)
        s = np.asarray(std, dtype=np.float32).reshape(1, -1, 1, 1)
        arr = (arr - m) / s
    return np.ascontiguousarray(arr)


def _softmax(x):
    x = np.asarray(x, dtype=np.float64).ravel()
    e = np.exp(x - x.max())
    return e / e.sum()


# ---------------------------------------------------------------- 模型
class Model:
    """统一推理入口。别直接 new，用 ai_runtime.load()"""

    def __init__(self, backend, raw, input_name=None, output_name=None,
                 input_size=224, normalize=True, path="", kind=""):
        self.backend = backend          # 'onnx' | 'torch' | 'stub'
        self.raw = raw                  # ort.InferenceSession | torch.nn.Module
        self.input_name = input_name
        self.output_name = output_name
        self.input_size = input_size
        self.normalize = normalize
        self.path = path
        self.kind = kind

    def __repr__(self):
        return "<Model %s backend=%s size=%s input=%s>" % (
            os.path.basename(self.path) or "(mem)", self.backend,
            _human_size(self.size_mb()), self.input_size)

    def size_mb(self):
        try:
            return os.path.getsize(self.path) / 1e6
        except Exception:  # noqa: BLE001
            return 0.0

    # ---- 通用 ----
    def predict(self, arr) -> np.ndarray:
        """喂 numpy 数组，返回输出数组。batch 恒定为 1，别传大批。"""
        arr = np.asarray(arr, dtype=np.float32)
        if self.backend == "onnx":
            if self.input_name is None:
                self.input_name = self.raw.get_inputs()[0].name
            return self.raw.run(None, {self.input_name: arr})[0]
        if self.backend == "torch":
            import torch
            with torch.no_grad():
                return self.raw(torch.from_numpy(arr)).numpy()
        raise RuntimeUnavailable("没有可用后端：%s" % self.backend)

    # ---- 图像 ----
    def predict_image(self, src, topk=5):
        """PIL.Image / 图片路径 -> [(类别下标, 概率), ...]

        返回的是下标；要名字自己带 labels.txt（一行一类）。
        """
        arr = _to_nchw(src, self.input_size, self.normalize)
        out = self.predict(arr)
        probs = _softmax(out)
        order = np.argsort(-probs)[:topk]
        return [(int(i), float(probs[i])) for i in order]

    # ---- 文本/特征 ----
    def predict_text(self, text, tokenizer=None, max_len=32):
        """文本 -> 模型原始输出（没做 softmax，分类自己接 _softmax）。

        tokenizer 必须给：手机端不内置分词器（体积 + 许可都不划算）。
        """
        if tokenizer is None:
            raise RuntimeUnavailable(
                "predict_text 需要显式传 tokenizer，例如：\n"
                "  m.predict_text('你好', tokenizer=lambda s: [ord(c) for c in s][:32])\n"
                "手机端不内置分词器；建议用训练时同一个 tokenizer 导出 ids 后走 predict()。")
        if self.backend != "onnx":
            raise RuntimeUnavailable("文本分支当前只保证 ONNX 通路；torch 分支请直接 predict(ids)")

        ids = list(tokenizer(text))[:max_len]
        inp = self.raw.get_inputs()[0]
        shape = [d if isinstance(d, int) else -1 for d in inp.shape]
        if len(shape) != 2:
            raise RuntimeUnavailable(
                "这个模型不是文本模型：输入形状是 %s，文本模型应是 [1, seq_len]。\n"
                "图像模型用 predict_image()，特征模型用 predict(arr)。" % (shape,))
        t = str(inp.type).lower()   # ort 给的是 "tensor(float)" / "tensor(int64)"
        dtype = np.float32 if "float" in t else np.int64
        seq = shape[1] if shape[1] > 0 else max_len
        arr = np.zeros((1, seq), dtype=dtype)
        for i, v in enumerate(ids[:seq]):
            arr[0, i] = v
        feed = {self.input_name or inp.name: arr}
        return self.raw.run(None, feed)[0]


def _human_size(mb: float) -> str:
    return "%.1f MB" % mb if mb >= 1 else "%.0f KB" % (mb * 1000)


# ---------------------------------------------------------------- 加载
def _check_size(path):
    if not os.path.isfile(path):
        raise FileNotFoundError("模型不存在：%s（把文件放到应用私有目录 models/ 下）" % path)
    mb = os.path.getsize(path) / 1e6
    if mb > HARD_SIZE_LIMIT_MB:
        raise ModelTooLarge(
            "模型 %.1f MB，超过硬上限 %d MB：手机上冷启动会卡死，"
            "先跑 tools/quantize_onnx.py 做 int8 动态量化，或换小模型。" % (mb, HARD_SIZE_LIMIT_MB))
    return mb


def load(path: str, input_size=224, normalize=True, providers=None, int8=False) -> Model:
    """加载模型。

    path:  .onnx（推荐，Pydroid/桌面直接可用）
           .pt  （torch 全量存档，仅 eval 小模型；需要 torch）
           .ptl / .pte —— 纯 Python 加载不了，会明确指路到 Java API
    """
    ext = os.path.splitext(path)[1].lower()
    mb = _check_size(path)

    if ext in (".ptl", ".pte"):
        raise UnsupportedFormat(
            "%s 是移动端序列化格式，纯 Python 侧没有加载器：\n"
            "  .ptl -> 在 Android 工程里用 PyTorch Mobile 的 Java API：\n"
            "          Module.load(assetFilePath(this, \"model.ptl\"))\n"
            "  .pte -> ExecuTorch 的 Java/Kotlin 运行时\n"
            "想在 Python 里跑，就先在 PC 上导出成 .onnx：torch.onnx.export(...)" % ext)

    if ext == ".onnx":
        ort = _try_import("onnxruntime")
        if ort is None:
            raise RuntimeUnavailable(
                "缺 onnxruntime：\n"
                "  Pydroid 3 / Termux / 桌面：pip install onnxruntime\n"
                "  打进 APK：需要 p4a 的 onnxruntime recipe（预编译 .so），纯 pip 装不进去\n"
                "  装不上就换 ExecuTorch / TFLite，别在手机上编译")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1     # 手机小模型：1 线程足够，省电
        opts.inter_op_num_threads = 1
        try:
            sess = ort.InferenceSession(
                path, opts, providers=providers or ["CPUExecutionProvider"])
        except Exception as exc:  # noqa: BLE001
            raise RuntimeUnavailable(
                "ONNX 加载失败：%r\n"
                "常见原因：算子不被移动端支持 / opset 过高 / ARM ABI 不匹配。\n"
                "建议：导出时开 dynamo=False、opset<=17，或转 TFLite。" % (exc,))
        inp = sess.get_inputs()[0]
        if mb > SOFT_SIZE_LIMIT_MB:
            print("! 模型 %.1f MB 偏大：建议 tools/quantize_onnx.py 做 int8 动态量化" % mb)
        if int8:
            print("i int8 量化应在 PC 上离线做；这里只做推理（如需量化跑 tools/quantize_onnx.py）")
        return Model("onnx", sess, input_name=inp.name,
                     input_size=input_size, normalize=normalize, path=path, kind=ext)

    if ext == ".pt":
        torch = _try_import("torch")
        if torch is None:
            raise RuntimeUnavailable(
                "缺 torch：Pydroid 3 / 桌面可 pip install torch --index-url "
                "https://download.pytorch.org/whl/cpu\n"
                "APK 别打包 torch（体积 + 启动时间都不划算）：先在 PC 转 .onnx 或 .ptl")
        try:
            obj = torch.load(path, map_location="cpu", weights_only=False)
        except TypeError:  # 老版本 torch 没有 weights_only
            obj = torch.load(path, map_location="cpu")
        mod = obj if hasattr(obj, "forward") else (
            obj.get("model") or obj.get("net") or obj)
        if not hasattr(mod, "forward"):
            raise RuntimeUnavailable(
                "这个 .pt 里没找到 nn.Module：退出 dict 里的 'model'/'net' 键，"
                "或先在 PC 上 torch.save(model, 'model.pt') 存整模型")
        if hasattr(mod, "eval"):
            mod.eval()
        if mb > SOFT_SIZE_LIMIT_MB:
            print("! torch 模型 %.1f MB：手机端只做 eval 小模型，别在这里训练" % mb)
        return Model("torch", mod, input_size=input_size, normalize=normalize,
                     path=path, kind=ext)

    raise UnsupportedFormat(
        "不认识的后缀 %s。支持 .onnx / .pt；.ptl 与 .pte 需 Java 层加载。" % ext)
