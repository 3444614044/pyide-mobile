# PyIDE Mobile

安卓轻量 Python 环境（Pydroid 3 简化版）。仓库：https://github.com/3444614044/pyide-mobile

- **MVP**：Kivy 三栏 IDE（文件 / 编辑器 / 输出）+ 运行 .py + numpy / PIL / pygame 示例
- **V2**：AI 运行器，`import ai_runtime` 做端侧推理（ONNX 优先，torch 兜底）
- **V3**：Quick Install 白名单 + 错误解释器 + buildozer.spec 成品化

---

## 1. 文件清单

**MVP**

| 文件 | 作用 |
|---|---|
| `main.py` | App 壳 + 事件转发（只管显示） |
| `ui.kv` | 三栏布局 + 安装面板规则 |
| `filetree.py` / `codearea.py` | 文件树 / 编辑器控件（无 pygments 自动退回原生） |
| `workspace.py` | 逻辑层：扫描 / 打开 / 保存 / 删除 / 运行（不依赖 widget，可无头测） |
| `runner.py` | 子进程执行 .py，流式回传输出，支持停止 |
| `uitest.py` / `selftest.py` | 无头自检 / 示例脚本自检 |
| `samples/01~04` | numpy 算力、pygame 触屏、PIL 写盘、环境体检 |

**V2**

| 文件 | 作用 |
|---|---|
| `ai_runtime.py` | `load()` / `predict()` / `predict_image()` / `predict_text()` |
| `aitest.py` | AI 自检：加载、推理、top-k、四条错误分支 |
| `samples/05~06` | 图像分类、非图像（特征 / 文本 ids）通路 |
| `tools/make_tiny_onnx.py` | 造迷你 ONNX 用于自检（不依赖 torch） |
| `tools/export_pt.py` | PC 上 .pt → .onnx / .ptl |
| `tools/quantize_onnx.py` | int8 动态量化 + 算子体检 |

**V3（新增）**

| 文件 | 作用 |
|---|---|
| `packages.py` | Quick Install 白名单：三档 + 安装命令 + buildozer requirements 生成 |
| `diag.py` | 错误解释器：traceback → 可执行建议（缺 wheel / 模型过大 / ARM 不兼容 / 改用 ONNX） |
| `pkgpanel.py` | 安装面板 UI（三档配色，实验档点下去先警告） |
| `v3test.py` | V3 自检：白名单 11 项 + 诊断 14 项 + 2 项集成 |
| `samples/07_diag_demo.py` | 诊断 + 白名单演示 |
| `alltest.py` | 一键跑四套自检 |

## 2. 安装命令

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install onnxruntime onnx          # V2 推理后端（Pydroid / 桌面）

python alltest.py     # 一键跑全部自检（4 套）
python main.py        # 起界面
```

手机上不要 pip install 这些，走打包。

## 3. AI 运行器怎么用

```python
import ai_runtime
m = ai_runtime.load("models/model.onnx")     # .onnx 推荐；.pt 需 torch
print(m.predict_image("cat.jpg", topk=3))    # -> [(类别下标, 概率), ...]
```

- 文本模型：`m.predict_text("你好", tokenizer=你的分词器)` —— 手机端不内置分词器，传 None 会明确报错指路。
- 三条红线：batch=1、输入 ≤224 或小特征维度、默认 int8 动态量化。
- **.ptl / .pte 在纯 Python 侧加载不了**，会明确指路到 Java API：`Module.load(assetFilePath(ctx, "model.ptl"))`。

## 4. Quick Install 白名单（V3）

工具条「📦」打开，只从白名单选，不开放自由输入。三档：

- **纯 Python（绿）**：pygments / markdown / tabulate / python-dateutil / attrs / tomli / rich
- **已验证 ARM wheel（蓝）**：numpy / Pillow / onnxruntime / regex / pyyaml / scipy / pandas
- **实验 / 建议 PC 训练（红）**：torch / tensorflow / opencv-python / matplotlib / scikit-learn / transformers / ultralytics —— 每条都给了替代方案

非纯 Python 一律强制 `--only-binary=:all:`：手机上不允许现场 gcc 编译，直接失败比卡 20 分钟好。
`packages.spec_requirements([...])` 会把选中的包转成 buildozer 的 requirements，并列出被拦下的包与原因。

## 5. 错误解释器（V3）

运行结束后自动对本次输出做匹配，命中就在输出面板追加「诊断建议」。覆盖：

| 症状 | 建议 |
|---|---|
| ModuleNotFoundError | 映射到正确 pip 包名（PIL→Pillow、cv2→headless 版等） |
| ImportError: cannot open shared object | ARM ABI 不匹配 / 需要 p4a recipe |
| SIGILL / SIGSEGV | 二进制指令集不对，换 aarch64 wheel |
| MemoryError / Killed | 模型过大：int8 量化、输入降到 224、batch=1 |
| opset / INVALID_GRAPH | 重新导出：opset≤17、dynamo=False |
| Permission denied / /system | 无 root 不能写 /system，改私有目录或 SAF |
| torch 相关 | 改 ONNX 或 .ptl / .pte |

正常输出不会误报（`diag.explain("OK")` 返回空）。

## 6. 打包 APK

```bash
pip install buildozer cython
buildozer -v android debug          # Linux / WSL / GitHub Actions，首次 20-40 分钟
adb install -r bin/*.apk
```

仓库自带 `.github/workflows/android.yml`：推 `v*` tag 或手动 dispatch，Actions 直接出 APK。

- requirements 只有 `python3,kivy,numpy,Pillow`，不含 pygame、不含 torch。
- onnxruntime 打进 APK 需要 p4a recipe；没有就走 .ptl / .pte 的 Java 路线。
- 只出 `arm64-v8a`；不申请存储权限，全部写应用私有目录。

## 7. 手机验证步骤

1. **最快（不打包）**：Pydroid 3 打开 `main.py`，看三栏、点示例运行。
2. **触屏**：跑 `samples/02_pygame_touch.py`，点中间按钮计数 +1、右上角 EXIT 退出。
3. **AI 通路**：把 `model.onnx` 放进 `projects/models/`，跑 `samples/05_ai_image.py`；没模型会自动造迷你 ONNX 演示。
4. **诊断**：跑 `samples/07_diag_demo.py`，看报错如何被翻译成可执行建议。
5. **装包面板**：点工具条「📦」，红档包点 Install 会先打印警告与替代方案。
6. **APK**：装包后跑 `01_numpy_demo.py` 看 MFLOPS；崩了 `adb logcat | grep python`。
7. 把 `alltest.py` 拷到手机（Pydroid）跑一遍，四套应全 OK。

## 8. 已知限制 / 失败回滚

- **无 root 不做的事**：不写 /system、不 sudo、不 apt。读写限制在应用私有目录，跨应用文件走 SAF（V4）。
- **pygame recipe 编不过**：从 requirements 摘掉，示例只在 Pydroid / 桌面跑，别为它上全量 gcc。
- **torch 不打包**：先在 PC 转 .onnx 或 .ptl。
- **回滚**：`git checkout mvp` / `v0.2.0` / `v0.3.0`；打包脏了 `buildozer android clean`，再不行删 `.buildozer`。

当前自检：`alltest.py` 四套全 OK（uitest 8 项、v3test 27 项、aitest 11 项、7 个示例）。
