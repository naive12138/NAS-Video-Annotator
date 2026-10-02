# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['faster_whisper', 'faster_whisper.transcribe', 'scenedetect', 'scenedetect.detectors', 'scenedetect.detectors.content_detector', 'scenedetect.video_stream', 'scenedetect.scene_manager', 'cv2', 'numpy', 'av', 'ctranslate2', 'onnxruntime']
hiddenimports += collect_submodules('faster_whisper')
hiddenimports += collect_submodules('scenedetect')


a = Analysis(
    ['C:/Users/LI/Desktop/新建文件夹/NAS-Video-Annotator/app/main.py'],
    pathex=['C:/Users/LI/Desktop/新建文件夹/NAS-Video-Annotator/app', 'C:/Users/LI/Desktop/新建文件夹/NAS-Video-Annotator/.deps'],
    binaries=[],
    datas=[('C:/Users/LI/Desktop/新建文件夹/NAS-Video-Annotator/app/db/schema.sql', 'db')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NAS-Video-Annotator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NAS-Video-Annotator',
)
