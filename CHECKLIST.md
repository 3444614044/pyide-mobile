# 真机验收清单

自动化测不了的部分（触屏手感、旋屏观感、真模型延迟）都在这里。
**先跑 `python devicecheck.py` 把自动项过一遍，再按本清单做人工确认** —— 自动项失败会直接告诉你修哪层。

## 验收顺序建议

**先在 Pydroid 3 上过一遍，确认通路后再打包 APK。**
打包一次 20–40 分钟，通路没通就打包是最浪费时间的做法。

```
第 1 步  Pydroid 3 打开 main.py        -> 过 P0-1 / P0-2 / P0-5
第 2 步  Pydroid 3 跑 devicecheck.py    -> 拿到自动项报告 + 延迟基线
第 3 步  按本清单做人工确认（触屏 / 旋屏 / 长任务）
第 4 步  通路确认 -> buildozer 打包     -> 过 P0-3 / P0-4 / P2
```

---

## P0 — 不通过就别发版

### P0-1 IDE 能起来并跑通示例
- **怎么做**：打开 App → 左侧应列出 8 个示例 → 点 `01_numpy_demo.py` → 点「运行」
- **通过判据**：输出面板出现 MFLOPS 数值和 `OK`；`[exit 0]`
- **失败怎么办**：
  - 白屏 / 秒退 → `adb logcat | grep python` 看 traceback，八成是 kv 里某个类没注册
  - 列表空 → 确认 `projects/` 私有目录可写（`devicecheck.py` 第 1 节会报）
  - `[exit 1]` 且无输出 → 子进程启动失败，看解释器路径报的对不对

### P0-2 AI 通路（真模型，不是迷你演示模型）
- **怎么做**：把你的 `model.onnx` 放到 `projects/models/` → 跑 `samples/05_ai_image.py`
- **通过判据**：打印出 top-k，且**单次推理 < 100ms**（batch=1、输入 224）
- **失败怎么办**：
  - 报缺 onnxruntime → Pydroid 里 `pip install onnxruntime`；APK 场景需要 p4a recipe，没有就走 .ptl
  - 报 opset / INVALID_GRAPH → PC 上重新导出 `opset_version=17, dynamo=False`
  - 超过 300ms → 先跑 `tools/quantize_onnx.py` 做 int8 动态量化，再不行换更小的模型
  - 报内存 → 输入降到 224 以下，或分块推理

### P0-3 旋屏不错位
- **怎么做**：竖屏 → 横屏 → 再转回来，来回三次；有折叠屏就展开/折叠一次
- **通过判据**：三栏比例自动变化（横屏时文件树明显变窄、输出面板变高），**无重叠、无空白、无控件跑出屏幕**
- **失败怎么办**：
  - 错位 = 某处写了死像素。布局必须走 `screen.layout_for()` 的比例值
  - 转屏后崩溃 = `on_resize` 里访问了还没建好的 ids，加空判断
  - 折叠屏跳档异常 = 检查是否按 **dp** 分档（`screen.width_class`），按像素判高 DPI 机会误判成平板

### P0-4 长任务被杀能续跑
- **怎么做**：跑 `samples/08_device_jobs.py` → 看「模拟进程被杀后重启」那段
- **真机补验**：起一个长任务 → 从最近任务列表划掉 App → 重新打开
- **通过判据**：启动时输出面板提示「发现未完成任务」，且能从断点继续，**不从 0 重跑**
- **失败怎么办**：进度文件在 `<私有目录>/projects/jobs/*.json`，确认它存在且 `done` 在增长；
  原子写（tmp + replace）保证被杀时不会留半个文件，若发现半截 JSON 说明这层被改坏了

### P0-5 不申请存储权限也能跑
- **怎么做**：系统设置里确认 App **没有**存储权限 → 新建文件、保存、运行
- **通过判据**：全部正常，无 Permission denied
- **失败怎么办**：有路径硬写了 `/sdcard` 或绝对路径。改回 `app.user_data_dir`；
  跨应用文件走 SAF，不要硬写

---

## P1 — 影响体验，尽量过

### P1-1 pygame 触屏
- **怎么做**：跑 `samples/02_pygame_touch.py`
- **通过判据**：手指点中间按钮计数 +1；右上角 EXIT 能退出；FPS 稳定在 55–60
- **失败怎么办**：
  - 点了没反应 = 只监听了 `MOUSEBUTTONDOWN`。真机只有 `FINGERDOWN`，示例里两个都接了
  - 布局错位 = 坐标写死了像素，必须按屏幕宽高百分比算
  - APK 里跑不了 = p4a 的 pygame recipe 没编过，**从 requirements 摘掉**，示例只在 Pydroid / 桌面跑

### P1-2 Quick Install 装包
- **怎么做**：点工具条「📦」→ 选一个绿档包（如 pygments）→ Install
- **通过判据**：输出面板出现 pip 日志且 `[pip exit 0]`
- **失败怎么办**：
  - APK 里提示「没有 pip」属**预期行为**（APK 默认不带 pip），改用 buildozer requirements
  - `--only-binary=:all:` 失败 = 这个包没有 aarch64 wheel，说明它不该进白名单

### P1-3 诊断命中真报错
- **怎么做**：写一个 `import cv2` 的脚本跑一下；再写一个除零的脚本
- **通过判据**：前者输出面板追加「诊断建议」并指到 `opencv-python-headless`
- **失败怎么办**：正常输出**不应该**弹建议。如果乱弹，说明 `diag.py` 规则误命中，把噪声行加进 `_NOISE`

### P1-4 电量节流
- **怎么做**：电量充到 90% 跑一次长任务，再等到 20% 以下跑一次
- **通过判据**：低电量时段间间隔明显变大（`device.power_budget` 返回 `low`）
- **失败怎么办**：电量读不到（`devicecheck.py` 显示 SKIP）属正常 —— 部分 ROM 不给权限，
  此时按常规模式跑，**不会**被误判成没电

---

## P2 — 有精力再补

### P2-1 多 ABI
- **怎么做**：`buildozer.spec` 里改成 `android.archs = arm64-v8a,armeabi-v7a` 重新打包
- **通过判据**：两种 ABI 的机器都能装能跑
- **代价**：包体接近翻倍、构建变长、部分 wheel 的 v7a 版本不好找
- **建议**：先用单 arm64 发版验证通路，确认有 v7a 需求再开

### P2-2 前台服务
- **怎么做**：`android.permissions` 加 `FOREGROUND_SERVICE`（Android 14 起还要细分类型），
  requirements 加 pyjnius → 重打包 → 调 `jobs.start_foreground()`
- **通过判据**：通知栏出现常驻通知，任务期间不易被杀
- **注意**：不做也**不影响正确性** —— 进度落盘已经保证被杀可续跑，前台服务只是加分项。
  没有 pyjnius 时 `start_foreground()` 会明确告知缺什么，不静默失败

---

## 报告回传

真机跑完这两条，把输出整段贴回来：

```bash
python devicecheck.py        # 自动项 + 延迟基线
python alltest.py            # 五套自检
```

重点关注报告里的三类信息：
- **失败项**：带 `[P0]` 的优先修
- **延迟数值**：`numpy 224 matmul` / `推理均值` / `PIL 预处理` 三个数，决定模型该怎么选
- **需人工项**：按上面清单逐条确认
