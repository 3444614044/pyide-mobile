# PyIDE Mobile — MVP

安卓轻量 Python 环境（Pydroid 3 简化版）的第一阶段：能装、能跑、能打包。

MVP 边界：文件树 + 编辑器 + 输出面板 + 运行 .py，附 numpy / PIL / pygame 触屏示例。
**不做**：pip 面板、AI 运行器、量化脚本（V2/V3）。

---

## 1. 文件清单（MVP 受影响文件）

| 文件 | 作用 |
|---|---|
| `main.py` | App 壳 + 事件转发（只管显示，不含业务逻辑） |
| `ui.kv` | 三栏布局：工具条 / 文件树 / 编辑器+输出 |
| `filetree.py` | 文件树控件 |
| `codearea.py` | 编辑器控件，有 pygments 就高亮，没有就退回原生 |
| `workspace.py` | **逻辑层**：扫描 / 打开 / 保存 / 删除 / 运行（不依赖 widget，可无头测） |
| `runner.py` | 子进程执行 .py，流式回传 stdout+stderr，支持停止 |
| `uitest.py` | 无头自检：逻辑层 + kv 语法 |
| `selftest.py` | 跑通 4 个示例脚本（pygame 用 dummy 驱动跑 5 秒） |
| `samples/01_numpy_demo.py` | numpy 算力粗测（224x224 上限 + 1x128 常规量） |
| `samples/02_pygame_touch.py` | pygame 触屏示例：全比例布局、只认手指、锁 60 帧 |
| `samples/03_pil_thumb.py` | PIL 生成 224 缩略图并写盘，验证私有目录可写 |
| `samples/04_env_probe.py` | 环境体检：ABI / 内存 / 可写目录（V2 选推理后端前先看它） |
| `buildozer.spec` | 最小可打包配置（当前只含 kivy+numpy+Pillow） |
| `requirements.txt` | 桌面调试依赖 |

## 2. 安装命令

桌面（Linux/macOS/WSL）：

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python uitest.py      # 逻辑自检，应全 PASS
python selftest.py    # 示例脚本自检，应全 PASS
python main.py        # 起界面
```

手机上**不要** pip install 这些，走打包（见下）。

## 3. 打包 APK

需要 Linux / WSL / GitHub Actions（buildozer 不支持在 Windows 原生打包）：

```bash
pip install buildozer cython
buildozer -v android debug          # 首次会下 SDK/NDK，约 20-40 分钟
adb install -r bin/*.apk
```

- 当前 `requirements = python3,kivy,numpy,Pillow`，**没挂 pygame**：p4a 的 pygame recipe 不是每个版本都能编过，编不过就别硬加，pygame 示例只在 Pydroid / 桌面跑。
- 只出 `arm64-v8a`，包体最小；要覆盖老机器再追加 `armeabi-v7a`。
- 不申请任何存储权限：全部写应用私有目录（`user_data_dir/projects`）。

## 4. 手机验证步骤

1. **最快（不打包）**：Pydroid 3 里打开 `main.py` 直接跑，看三栏是否出现、能否点示例运行。
2. **示例单独验证**：Pydroid 3 直接跑 `samples/02_pygame_touch.py`，手指点中间按钮计数 +1，右上角 EXIT 退出 → 触屏与比例布局 OK。
3. **APK 验证**：装包后打开 → 左侧应列出 4 个示例 → 点 `01_numpy_demo.py` → 运行 → 输出面板出现 MFLOPS 与 `OK`。
4. **崩溃看日志**：`adb logcat | grep python`。
5. **无头自检同一套**：把 `uitest.py` 拷到手机（Pydroid）跑一遍，逻辑层应全 PASS。

## 5. 已知限制 / 失败回滚

- **无 root 不做的事**：不写 /system、不 sudo、不 apt。所有读写限制在应用私有目录，跨应用文件后续用 SAF（V4）。
- **pygame recipe 编不过**：从 `buildozer.spec` 的 requirements 里删掉 pygame，示例仅在 Pydroid/桌面跑；不要为它加 gcc 全量编译。
- **回滚**：每个阶段打 tag，出问题直接回去。
  ```bash
  git tag mvp && git checkout mvp       # 回到 MVP
  buildozer android clean               # 打包脏了先清
  rm -rf .buildozer                     # 还不行就删构建缓存（下次全量重编）
  ```

当前自检结果：逻辑层 7 项全 PASS；4 个示例脚本全 PASS；
`ui.kv 规则可解析` 在无 GL 的 CI/容器里会显示 SKIP（属环境限制，桌面或手机上是 PASS）。
