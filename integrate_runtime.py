# -*- coding: utf-8 -*-
"""Windows 运行环境集成：把 VC++ 2015-2022 运行库等系统 DLL 一并拷进 exe 的 _internal 目录，
让目标机器即使没有安装 VC++ Redistributable 也能直接双击运行。

用法：
    python integrate_runtime.py            # 只补运行库到现有 dist
    python integrate_runtime.py --build    # 先执行 build.py 再补运行库

（build.py 在打包成功后也会自动调用本脚本补齐运行库。）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# VC++ 2015-2022 运行库（64 位）全套。
# PyInstaller 通常只带 vcruntime140 / msvcp140 少数几个；
# 这里把 onnxruntime / ctranslate2 / PySide6 / numpy 等可能依赖的都补齐。
VC_RUNTIME_DLLS = [
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "concrt140.dll",
    "vccorlib140.dll",
    "vcomp140.dll",
]


def _system32() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"


def _locate(name: str) -> Path | None:
    candidates = [
        _system32() / name,                       # 系统运行库（最全）
        Path(sys.executable).resolve().parent / name,  # Python 自带目录
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def integrate(internal_dir: Path) -> tuple[list[str], list[str]]:
    """把缺失的 VC++ 运行库拷进 _internal，返回 (已复制列表, 未找到列表)。"""
    internal_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    missing: list[str] = []
    for name in VC_RUNTIME_DLLS:
        dst = internal_dir / name
        if dst.is_file():
            continue
        src = _locate(name)
        if src:
            shutil.copy2(src, dst)
            copied.append(name)
        else:
            missing.append(name)
    return copied, missing


def verify(internal_dir: Path) -> list[str]:
    """校验打包产物关键部件，返回问题列表。"""
    problems: list[str] = []
    qwindows = internal_dir / "PySide6" / "plugins" / "platforms" / "qwindows.dll"
    if not qwindows.is_file():
        problems.append("Qt 平台插件 qwindows.dll 缺失")
    for name in VC_RUNTIME_DLLS:
        if not (internal_dir / name).is_file():
            problems.append(f"运行库缺失：{name}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="补齐 Windows 运行库到 PyInstaller 产物")
    ap.add_argument("--build", action="store_true", help="先执行 build.py 再补运行库")
    ap.add_argument("--dist", default=None, help="dist 目录（默认自动定位）")
    args = ap.parse_args()

    project = Path(__file__).resolve().parent
    dist = Path(args.dist) if args.dist else project / "dist" / "NAS-Video-Annotator"
    internal = dist / "_internal"

    if args.build:
        print("[1/3] 执行 PyInstaller 打包 build.py …")
        rc = subprocess.run([sys.executable, str(project / "build.py")], cwd=project).returncode
        if rc != 0:
            print("[!] 打包失败，退出")
            return rc

    print("[2/3] 补齐 Windows 运行库到 _internal …")
    copied, missing = integrate(internal)
    for n in copied:
        print(f"    + {n}")
    for n in missing:
        print(f"    - 未找到（本机未安装该运行库）: {n}")

    print("[3/3] 校验…")
    problems = verify(internal)
    if problems:
        for p in problems:
            print("    !", p)
    else:
        print("    校验通过：运行库 + Qt 平台插件均已就位")
    print(f"完成：{dist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
