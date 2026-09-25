# PyIDE Mobile

安卓轻量 Python 环境（Pydroid 3 简化版）。仓库：https://github.com/3444614044/pyide-mobile

- **MVP**：Kivy 三栏 IDE（文件 / 编辑器 / 输出）+ 运行 .py + numpy / PIL / pygame 示例
- **V2**：AI 运行器，`import ai_runtime` 做端侧推理（ONNX 优先，torch 兜底）

---

## 1. 文件清单

**MVP**

| 文件 | 作用 |
|---|---|
| `main.py` | App 壳 + 事件转发（只管显示） |
| `ui.kv` | 三栏布局 |
| `filetree.py` / `codearea.py` | 文件树 / 编辑器控件（无 pygments 自动退回原生） |
| `workspace.py` | 逻辑层：扫描 / 打开 / 保存 / 删除 / 运行（不依赖 widget，可无头测） |
| `runner.py` | 子进程执行 .py，流式回传输出，支持停止 |
| `uitest.py` / `selftest.py` | 无头自检 / 示例脚本自检 |
| `samples/01~04` | numpy 算力、pygame 触屏、PIL 写盘、环境体检 |

**V2（新增）**

| 文件 | 作用 |
|---|---|
| `ai_runtime.py` | 统一推理入口：`load()` / `predict()` / `predict_image()` / `predict_text()` |
| `aitest.py` | AI 自检：加载、推理、top-k、四条错误分支 |
| `samples/05_ai_image.py` | 图像分类示例（没模型会自动造迷你 ONNX 演示通路） |
| `samples/06_ai_feature.py` | 非图像输入：特征向量 + 文本 ids 两条通路 |
| `tools/make_tiny_onnx.py` | 生成迷你 ONNX（不依赖 torch，用于自检） |
| `tools/export_pt.py` | PC 上把 .pt 导出成 .onnx / .ptl |
| `tools/quantize_onnx.py` | int8 动态量化 + 模型体检 |

## 2. 安装命令

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install onnxruntime onnx          # V2 推理后端（Pydroid / 桌面）

python uitest.py      # 逻辑层自检
python aitest.py      # AI 运行器自检
python selftest.py    # 6 个示例脚本
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
- 体检：`ai_runtime.backend_report()` 打印 onnxruntime / torch / ABI / providers。
- 三条红线：batch=1、输入 ≤224 或小特征维度、默认 int8 动态量化。
- **.ptl / .pte 在纯 Python 侧加载不了**，会明确指路到 Java API：
  `Module.load(assetFilePath(ctx, "model.ptl"))`（PyTorch Mobile）/ ExecuTorch 运行时。

## 4. 打包 APK

```bash
pip install buildozer cython
buildozer -v android debug          # Linux / WSL / GitHub Actions，首次 20-40 分钟
adb install -r bin/*.apk
```

仓库里已带 `.github/workflows/android.yml`：推 `v*` tag 或手动 dispatch 就能在 Actions 上出 APK（artifact 下载）。

- 当前 requirements 只有 `python3,kivy,numpy,Pillow`，不含 pygame、不含 torch。
- onnxruntime 打进 APK 需要 p4a recipe（预编译 .so），不是 pip 一下就好；没有 recipe 就走 .ptl / .pte 的 Java 路线。
- 只出 `arm64-v8a`；不申请存储权限，全部写应用私有目录。

## 5. 手机验证步骤

1. **最快（不打包）**：Pydroid 3 打开 `main.py`，看三栏、点示例运行。
2. **触屏**：跑 `samples/02_pygame_touch.py`，点中间按钮计数 +1、右上角 EXIT 退出。
3. **AI 通路**：把 `model.onnx` 放进私有目录 `projects/models/`，跑 `samples/05_ai_image.py`；没模型也会自动造迷你 ONNX 演示。
4. **APK**：装包后跑 `01_numpy_demo.py` 看 MFLOPS；崩了 `adb logcat | grep python`。
5. 把 `uitest.py` / `aitest.py` 拷到手机（Pydroid）跑一遍，逻辑层应全 PASS。

## 6. 已知限制 / 失败回滚

- **无 root 不做的事**：不写 /system、不 sudo、不 apt。读写限制在应用私有目录，跨应用文件走 SAF（V4）。
- **pygame recipe 编不过**：从 requirements 摘掉，示例只在 Pydroid / 桌面跑，别为它上全量 gcc。
- **torch 不打包**：体积和冷启动都不划算，先在 PC 转 .onnx 或 .ptl。
- **回滚**：`git checkout mvp`（MVP 快照）；打包脏了 `buildozer android clean`，再不行删 `.buildozer`。

当前自检：逻辑层 7 项 PASS（`ui.kv` 在无 GL 容器里显示 SKIP，桌面/手机 PASS）、
AI 自检 10 项 PASS、6 个示例脚本 PASS。
