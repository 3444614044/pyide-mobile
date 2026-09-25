# PyIDE Mobile — buildozer 配置（V3 成品化）
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
source.exclude_dirs = bin,.buildozer,__pycache__,.git,models

version = 0.3.0

# ---------------------------------------------------------------- requirements
# 只放有 p4a recipe 且确实需要的东西。每加一个，包体和启动时间都实打实变长。
#
# 当前：kivy(UI) + numpy + Pillow(AI 预处理)。已经够跑 MVP 与 V2 的图像通路。
requirements = python3,kivy,numpy,Pillow

# 想加语法高亮就补 pygments（纯 Python，几乎不增加体积）：
# requirements = python3,kivy,numpy,Pillow,pygments

# ---- 关于 onnxruntime（V2 AI 运行器）----
# Pydroid / 桌面：pip install onnxruntime 即可，ai_runtime 直接可用。
# 打进 APK：需要 p4a 的 onnxruntime recipe（预编译 .so），纯 pip 装不进去。
#   - 有 recipe：把它加进上面的 requirements，AI 运行器在 APK 里也能跑 onnx
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

orientation = portrait          # V4 会改成 sensor（横竖屏），先竖屏稳住布局
fullscreen = 0
android.permissions =           # 不申请存储权限：全部写应用私有目录
android.api = 35
android.minapi = 23

# ABI：先只出 arm64-v8a（包体最小、性能最好）。要覆盖老机器再加 armeabi-v7a，
# 代价是包体翻倍、且部分 wheel 的 v7a 版本不好找。
android.archs = arm64-v8a
# android.archs = arm64-v8a,armeabi-v7a

p4a.branch = master

# 端侧注意：不申请存储权限，全部写应用私有目录（user_data_dir/projects），
# 跨应用文件走 SAF（存储访问框架）—— V4 再做。

# V4 待补（本版未启用，先留位）：
#   orientation = sensor                         # 横竖屏
#   android.permissions = FOREGROUND_SERVICE     # 长任务前台服务
#   android.add_src =                            # 需要 .ptl 的 Java 加载器时再挂

[buildozer]
log_level = 2
warn_on_root = 1

# 构建脏了的处理顺序：
#   buildozer android clean      # 先试这个
#   rm -rf .buildozer            # 还不行就删缓存（下次全量重编，慢但干净）
