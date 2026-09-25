# PyIDE Mobile — MVP 最小可打包配置
# 打包命令：buildozer -v android debug   （需 Linux / WSL / GitHub Actions）
[app]
title = PyIDE Mobile
package.name = pyidemobile
package.domain = org.tinyide

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,md,ttf
source.include_patterns = samples/*,tools/*
# 模型不入包（体积），运行时用 SAF 或 adb push 到应用私有目录
source.exclude_dirs = bin,.buildozer,__pycache__,.git,models

version = 0.2.0

# MVP 先不挂 pygame：p4a 的 pygame recipe 并非每个版本都能编过。
# 编不过就保持下面这一行，pygame 示例只在 Pydroid / 桌面里跑。
#
# AI 运行器（V2）：
#   Pydroid / 桌面  -> pip install onnxruntime，ai_runtime 直接可用
#   打进 APK        -> 需要 p4a 的 onnxruntime recipe（预编译 .so），
#                      纯 pip 装不进去；没有 recipe 就走
#                      PyTorch Mobile Java(.ptl) / ExecuTorch(.pte)
requirements = python3,kivy,numpy,Pillow

orientation = portrait
fullscreen = 0
android.permissions =
android.api = 35
android.minapi = 23
# 优先只出 arm64-v8a，包体最小；要覆盖老机再加 armeabi-v7a
android.archs = arm64-v8a
p4a.branch = master

# 端侧注意：不申请存储权限，全部写应用私有目录（user_data_dir）
[buildozer]
log_level = 2
warn_on_root = 1

# 排错：buildozer android logcat | grep python
