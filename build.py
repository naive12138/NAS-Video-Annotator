# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本（在项目根目录运行：python build.py）。

要求：
- 已执行 `pip install pyinstaller`
- 项目 .deps 目录已包含 PySide6 及分析依赖（faster-whisper / scenedetect）
- 系统 PATH 中有 ffmpeg/ffprobe（可选，若存在则一并打包进 exe）

产物输出到 dist/NAS-Video-Annotator/。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(project, "app")
    deps = os.path.join(project, ".deps")
    schema = os.path.join(app_dir, "db", "schema.sql")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", "NAS-Video-Annotator",
        "--paths", app_dir,
        "--paths", deps,
        "--add-data", f"{schema};db",
    ]

    # 分析相关为“懒加载”，需显式声明 hidden-import，否则 PyInstaller 检测不到
    for h in [
        "faster_whisper", "faster_whisper.transcribe",
        "scenedetect", "scenedetect.detectors", "scenedetect.detectors.content_detector",
        "scenedetect.video_stream", "scenedetect.scene_manager",
        "cv2", "numpy", "av", "ctranslate2", "onnxruntime",
    ]:
        cmd += ["--hidden-import", h]
    for sub in ["faster_whisper", "scenedetect"]:
        cmd += ["--collect-submodules", sub]

    for exe in ("ffmpeg", "ffprobe"):
        p = shutil.which(exe)
        if p:
            cmd += ["--add-binary", f"{p};."]
            print(f"[build] 已附加 {exe}: {p}")
        else:
            print(f"[build] 未找到 {exe}（跳过，运行时需自行提供）")

    cmd.append(os.path.join(app_dir, "main.py"))
    print("[build] 运行:", " ".join(cmd))
    rc = subprocess.run(cmd, cwd=project, check=False).returncode
    if rc == 0:
        guide = os.path.join(project, "初次使用说明.txt")
        if os.path.exists(guide):
            dst = os.path.join(project, "dist", "NAS-Video-Annotator", "初次使用说明.txt")
            shutil.copy(guide, dst)
            print(f"[build] 已复制初次使用说明 -> {dst}")

        # 补齐 Windows 运行库（VC++ Redistributable 等），确保目标机器无需预装即可运行
        try:
            sys.path.insert(0, project)
            from integrate_runtime import integrate, verify
            internal = Path(project) / "dist" / "NAS-Video-Annotator" / "_internal"
            copied, missing = integrate(internal)
            for n in copied:
                print(f"[runtime] + {n}")
            for n in missing:
                print(f"[runtime] - 未找到 {n}")
            for p in verify(internal):
                print(f"[runtime] ! {p}")
        except Exception as e:  # noqa: BLE001
            print(f"[runtime] 运行库补齐失败（不阻断打包）: {e}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
