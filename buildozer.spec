# PyIDE Mobile — buildozer 配置（V4 成品化）
#
# 打包：buildozer -v android debug      （Linux / WSL / GitHub Actions）
# 装包：adb install -r bin/*.apk
# 排错：adb logcat | grep python
#
# 这个文件里的注释都是踩过坑的结论，改动前先读一遍。

[app]
title = PyIDE Mobile
package.name = pyidemobile
package.domain = org.tinyide

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,md,ttf
source.include_patterns = samples/*,tools/*
# 模型不入包（体积 + 冷启动），运行时放应用私有目录 projects/models/
# jobs/ 是运行期进度文件，也不入包
source.exclude_dirs = bin,.buildozer,__pycache__,.git,models,jobs

version = 0.4.0

# ---------------------------------------------------------------- requirements
# 只放有 p4a recipe 且确实需要的东西。每加一个，包体和启动时间都实打实变长。
requirements = python3,kivy,numpy,Pillow

# 想加语法高亮就补 pygments（纯 Python，几乎不增加体积）：
# requirements = python3,kivy,numpy,Pillow,pygments

# ---- 关于 onnxruntime（V2 AI 运行器）----
# Pydroid / 桌面：pip install onnxruntime 即可，ai_runtime 直接可用。
# 打进 APK：需要 p4a 的 onnxruntime recipe（预编译 .so），纯 pip 装不进去。
#   - 有 recipe：加进 requirements，AI 运行器在 APK 里也能跑 onnx
#   - 没有 recipe：别硬加。改走 PyTorch Mobile 的 .ptl（Java API
#     Module.load(assetFilePath(ctx,"model.ptl"))）或 ExecuTorch 的 .pte
# packages.py 里 onnxruntime 的 p4a 字段特意留空，就是提醒这一点。

# ---- 关于 pygame ----
# p4a 的 pygame recipe 不是每个版本都能编过；编不过就别加，
# pygame 示例（samples/02）只在 Pydroid / 桌面上跑。
# 别为了它去装 gcc 全量编译栈 —— 本项目的约束是"不假设能编译"。

# ---- 关于 torch ----
# 不要打进 APK：CPU wheel 本体 200MB+，冷启动和内存都撑不住。
# 需要的话在 PC 上 torch.onnx.export 导出 .onnx，手机只做推理。

# ---------------------------------------------------------------- V4：横竖屏
# sensor = 跟随系统旋屏。注意：旋屏会重建窗口，布局必须按 dp 比例算，
# 本项目用 screen.layout_for() 在 on_resize 里重算，不写死像素。
orientation = sensor
# 只锁竖屏就改回 portrait；游戏类示例建议 portrait，编辑器建议 sensor。

fullscreen = 0

# ---------------------------------------------------------------- V4：权限
# 不申请存储权限：全部写应用私有目录（user_data_dir/projects），跨应用文件走 SAF。
android.permissions =
#
# 长任务要前台服务时再开（Android 14 起还要细分类型）：
# android.permissions = FOREGROUND_SERVICE,FOREGROUND_SERVICE_DATA_SYNC
# 同时 requirements 加 pyjnius，jobs.start_foreground() 才会真正生效；
# 没有 pyjnius 时它会明确告知缺什么，不静默失败 —— 进度落盘已保证被杀可续跑。

android.api = 35
android.minapi = 23

# ---------------------------------------------------------------- V4：多 ABI
# arm64-v8a：包体最小、性能最好，覆盖 2016 年后的绝大多数机器。
android.archs = arm64-v8a
#
# 要覆盖老机器就两个一起出，代价：
#   - 包体接近翻倍
#   - 部分 wheel 的 armeabi-v7a 版本不好找（onnxruntime 官方就有 arm64 优先的差别）
#   - 构建时间变长
# android.archs = arm64-v8a,armeabi-v7a
#
# 建议：先用 arm64 单 ABI 发一版验证通路，确认有 v7a 需求再开双 ABI。

p4a.branch = master

# 端侧注意：不申请存储权限，全部写应用私有目录，
# 跨应用文件走 SAF（存储访问框架）—— 目前定位为后续迭代项。

[buildozer]
log_level = 2
warn_on_root = 1

# 构建脏了的处理顺序：
#   buildozer android clean      # 先试这个
#   rm -rf .buildozer            # 还不行就删缓存（下次全量重编，慢但干净）
