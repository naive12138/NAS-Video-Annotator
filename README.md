# NAS 视频内容分析与标注系统

对 Windows 局域网 NAS 中的视频做**本地 AI 内容分析**（场景、人数、题材、剧情概括），
并把精简结果自动写回 **Jellyfin 简介栏** 或 **视频同目录 `.txt` / `.nfo`**。全程本地运行，视频内容不出本机。

## 功能特性

- 双视频源：**本地路径**（含 NAS 挂载盘符/UNC）与 **Jellyfin API**（分析走 Jellyfin 流接口，无需挂载盘符）。
- 全本地 AI：场景描述、人数、题材、剧情、标签均由本地视觉/文本 LLM 产出；语音转写用本地 faster-whisper。不依赖 YOLO/torch、不依赖任何云端。
- 回写自动绑定数据源：本地 → 同名 `.nfo`（无则写 `简介{视频名}.txt`）；Jellyfin → 更新简介栏。
- 兼容 **Ollama** 与 **OpenAI 兼容接口**（llama.cpp / LM Studio / vLLM），自动探测。
- 便携：所有数据（配置、数据库、缓存、ffmpeg、转写模型）都在 exe 同目录的 `data\` 下。

## 目录结构

```
app/
  main.py                 # 入口：python app/main.py
  core/                   # 核心引擎（不依赖 GUI，可单独测试）
    config.py             # 配置中心（便携 data\config.json）
    readiness.py          # 模型就绪检测（“测试”按钮后端）
    store.py              # SQLite 存储 / 检索 / 删除
    media.py              # ffprobe / 抽帧 / 场景切分 / 音轨
    summarize.py          # 提示词 + 汇总（题材/剧情/标签/人数）
    condense.py           # 标注 → 精简回写文本
    writeback.py          # 回写执行（按数据源自动选 txt/nfo/Jellyfin）
    pipeline.py           # 单视频分析流水线 + 进度 + 自动清理
    task_queue.py         # 后台任务队列
    ffmpeg.py             # ffmpeg 检测 / 一键下载
    sources/              # local / jellyfin 视频源适配
    models/               # ollama_client（兼容 OpenAI）/ asr
    writers/              # txt / nfo / jellyfin 回写器
  gui/                    # PySide6 界面（设置/媒体库/分析任务/日志/检索/错误）
  db/schema.sql           # 数据库结构
docs/                     # 开发文档
tests/                    # 单元测试
build.py                  # PyInstaller 打包脚本
```

## 环境准备（用户侧）

1. **Python 3.11+**（仅从源码运行时需要；用 exe 则不需要）。
2. **ffmpeg / ffprobe**：软件设置页可“一键下载”；或手动放到 exe 同目录 / `data\bin\`。
3. **本地大模型**：Ollama（`ollama pull qwen2.5vl:7b`、`ollama pull qwen2.5:7b`）或 llama.cpp/LM Studio（OpenAI 兼容接口）。
4. 从源码运行时的 Python 依赖：
   ```powershell
   pip install --target .deps PySide6==6.11.2 faster-whisper scenedetect
   ```

## 运行（开发态）

```powershell
python app\main.py
```

首次启动会在 **exe/项目同目录的 `data\`** 生成 `config.json` 与 `nasva.db`（便携模式）。
所有配置在软件「设置」页修改；「测试」按钮只检测模型是否就绪，不推理。

## 运行测试

```powershell
python tests\test_config.py
python tests\test_readiness.py
python tests\test_store.py
python tests\test_sources_local.py
python tests\test_summarize.py
python tests\test_condense_writers.py
python tests\test_jellyfin.py
python tests\test_pipeline.py
python tests\test_task_queue.py
python tests\test_llm_client.py
python tests\test_media.py
python tests\test_asr.py
python tests\test_gui_smoke.py   # 需本机可加载 PySide6
```

## 打包为 exe

```powershell
pip install pyinstaller
python build.py
```

产物在 `dist\NAS-Video-Annotator\`，并会自动附带 `初次使用说明.txt`。
若系统无 ffmpeg，请把 `ffmpeg.exe`/`ffprobe.exe` 放到 exe 同目录或 `data\bin\`。

## 回写规则

| 视频来源 | 自动回写位置 |
|----------|--------------|
| 本地路径 | 优先写同名 `.nfo`（`<plot>`/`<outline>`）；无 `.nfo` 则写 `简介{视频名}.txt` |
| Jellyfin | 调 API 更新 `Overview`（简介栏） |

## 更多文档

- `docs/架构与模块说明.md`：架构、流水线、配置、数据库、提示词、扩展点。
- `初次使用说明.txt`：给最终用户的图文式上手说明。

## 许可证

见 `LICENSE`（MIT）。
