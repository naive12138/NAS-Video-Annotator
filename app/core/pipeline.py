# -*- coding: utf-8 -*-
"""单视频分析流水线：预处理 → 分析 → 汇总 → 落库 → 精简回写（见计划书 §6）。"""
from __future__ import annotations

import base64
import shutil
import traceback
from pathlib import Path
from typing import Callable

from . import audio_analysis, ffmpeg as _ffmpeg, media, summarize, writeback as _writeback
from .config import Config
from .models import asr as _asr
from .models.ollama_client import OllamaClient
from .sources.base import VideoSource
from .store import Store


class CancelledError(Exception):
    """任务被用户取消时抛出，用于中断流水线。"""


class Pipeline:
    def __init__(
        self,
        cfg: Config,
        store: Store,
        client: OllamaClient | None = None,
        transcribe: Callable | None = None,
    ):
        self.cfg = cfg
        self.store = store
        self.client = client or OllamaClient(
            cfg.ollama["base_url"], cfg.ollama["timeout_s"],
            generate_timeout_s=cfg.ollama.get("generate_timeout_s"),
        )
        self.transcribe = transcribe or _asr.transcribe

    def run(self, video: VideoSource, on_progress=None, cancel_event=None) -> dict:
        self._cancel_event = cancel_event
        store = self.store
        store.init_schema()
        media.register_bin_dir(_ffmpeg.bin_dir(self.cfg))

        base = {
            "source_type": video.source_type,
            "jellyfin_item_id": video.jellyfin_item_id,
            "file_path": video.file_path,
            "title": video.title or Path(video.file_path).stem,
        }
        vid = store.upsert_video(base)
        store.set_video_status(vid, "processing")
        run_id = store.save_run({
            "video_id": vid, "status": "processing",
            "model_name": self.cfg.models["llm"],
        })

        try:
            self._progress(on_progress, 5, self._stage(video, "读取视频信息"))
            self._check_cancel()
            meta = media.probe(self._media_src(video))
            store.upsert_video({**base, **meta})
            annotation = self._analyze(video, vid, run_id, meta.get("duration_sec") or 0.0, on_progress)
            self._progress(on_progress, 95, "写入标注与回写")
            store.save_annotation({"video_id": vid, "run_id": run_id, **annotation})
            store.set_video_status(vid, "done")
            store.update_run(run_id, status="done")
            self._writeback(video, vid, annotation)
            self._progress(on_progress, 100, "完成")
            self._cleanup(vid)
            self._cleanup_ai_context()
            return annotation
        except CancelledError:
            store.set_video_status(vid, "cancelled")
            store.update_run(run_id, status="cancelled", error_msg="已取消")
            raise
        except Exception as e:
            tb = traceback.format_exc()
            store.set_video_status(vid, "failed")
            store.update_run(run_id, status="failed", error_msg=tb)
            store.record_error(vid, "analyze", tb, video.file_path)
            raise

    @staticmethod
    def _progress(on_progress, percent: int, message: str) -> None:
        if on_progress:
            try:
                on_progress(percent, message)
            except Exception:
                pass

    def _check_cancel(self) -> None:
        if getattr(self, "_cancel_event", None) and self._cancel_event.is_set():
            raise CancelledError()

    @staticmethod
    def _media_src(video: VideoSource) -> str:
        """分析用的媒体输入：Jellyfin 源优先用流地址，本地源用文件路径。"""
        return video.stream_url or video.file_path

    @staticmethod
    def _stage(video: VideoSource, msg: str) -> str:
        """Jellyfin 源提示正在缓冲；本地源保持原样。"""
        if getattr(video, "source_type", None) == "jellyfin":
            return f"{msg}（Jellyfin 缓冲中）"
        return msg

    def _cleanup(self, vid: int) -> None:
        """清理本视频的临时文件（抽帧图片、临时音轨）。"""
        d = self.cfg.storage_path("frame_cache_dir") / str(vid)
        shutil.rmtree(d, ignore_errors=True)

    def _cleanup_ai_context(self) -> None:
        """尽量卸载模型以释放上下文/显存（不清理提示词，也不清理标注/检索数据）。"""
        unload = getattr(self.client, "unload", None)
        if not unload:
            return
        for m in (self.cfg.models.get("vision"), self.cfg.models.get("llm")):
            if m:
                try:
                    unload(m)
                except Exception:
                    pass

    # ---- 内部分析 ----
    def _analyze(self, video: VideoSource, vid: int, run_id: int, duration: float,
                 on_progress=None) -> dict:
        cfg = self.cfg
        store = self.store
        self._check_cancel()

        # 0. 提前抽音轨（供方案 A/B 音频分析 + ASR + 翻译复用）
        audio_path = None
        silent_times: list[float] = []
        try:
            audio_path = media.extract_audio(
                self._media_src(video),
                cfg.storage_path("frame_cache_dir") / str(vid) / "audio.wav",
            )
            if audio_path and Path(audio_path).exists():
                silent_times = audio_analysis.silent_times(
                    audio_analysis.rms_curve(audio_path)
                )
        except Exception:
            audio_path, silent_times = None, []
        self._progress(on_progress, 10, self._stage(video, "音频分析"))

        # 1. 音频转写 + 翻译（提前到场景切片之前，便于快速测试/看到结果）
        transcript_text, transcript_segments, asr_info = self._transcribe(video, vid, run_id, audio_path)
        transcript_zh = ""
        if transcript_text and not summarize.is_chinese_text(transcript_text):
            try:
                transcript_zh = summarize.translate_to_chinese(transcript_text, self._llm)
            except Exception:
                transcript_zh = ""
        self._save_transcript_files(vid, transcript_text, transcript_zh)
        summary_transcript = transcript_zh or transcript_text  # 汇总用中文

        # 1.1 把长字幕总结成简短剧情概括，缓解上下文过长导致的 bug
        transcript_summary = ""
        if summary_transcript:
            try:
                transcript_summary = summarize.summarize_transcript(summary_transcript, self._llm)
            except Exception:
                transcript_summary = ""
        final_transcript = transcript_summary or summary_transcript  # 参与最终汇总

        # 方案 B：音频结构文字线索（静音 + 对白分布 → 辅助识别片头片尾）
        audio_clue = ""
        try:
            if silent_times:
                speech = [(s["start"], s["end"]) for s in transcript_segments]
                audio_clue = audio_analysis.build_audio_clue(
                    audio_analysis.silence_segments(silent_times), speech, duration
                )
        except Exception:
            audio_clue = ""

        self._write_debug_file(video, transcript_text, transcript_zh, [], asr_info, transcript_summary)
        self._progress(on_progress, 15, self._stage(video, "音频转写"))

        # 2. 场景切分（方案 A：用音频停顿合并被误切的快剪场景）
        scenes = media.detect_scenes(self._media_src(video), cfg.analysis["scene_threshold"])
        if silent_times:
            scenes = audio_analysis.merge_scenes_by_audio(scenes, silent_times)
        store.save_scenes([
            {"video_id": vid, "run_id": run_id, "scene_index": i,
             "start_sec": s, "end_sec": e}
            for i, (s, e) in enumerate(scenes)
        ])
        self._progress(on_progress, 20, self._stage(video, "场景切分"))

        # 3. 抽帧（场景代表帧 + 均匀帧）
        times = self._frame_times(scenes, duration)
        out_dir = cfg.storage_path("frame_cache_dir") / str(vid)
        frame_paths = media.extract_frames(self._media_src(video), out_dir, times)
        self._progress(on_progress, 25, self._stage(video, "抽帧"))

        # 4. 视觉理解（逐帧）：描述 + 人数，均由本地视觉 LLM 产出；同时留存模型原文供调试文本
        scene_descriptions: list[str] = []
        people_counts: list[int | None] = []
        image_raws: list[str] = []
        total = max(len(frame_paths), 1)
        for i, fp in enumerate(frame_paths):
            self._check_cancel()
            self._progress(on_progress, 30 + int(55 * i / total), f"AI 分析第 {i + 1}/{total} 帧")
            desc, n, raw = self._describe_frame(fp)
            scene_descriptions.append(desc)
            people_counts.append(n)
            image_raws.append(raw)
            store.save_frames([{
                "video_id": vid, "scene_id": None, "image_path": str(fp),
                "description": desc, "people_count": n,
            }])
            # 实时输出图片理解原文（若开启参考文本测试）
            self._write_debug_file(video, transcript_text, transcript_zh, image_raws, asr_info, transcript_summary)

        # 5. 汇总（字幕用简短剧情概括，避免上下文过长）
        self._check_cancel()
        self._progress(on_progress, 85, "汇总剧情")
        annotation = summarize.summarize(
            scene_descriptions, final_transcript, self._llm, audio_clue=audio_clue,
            max_scene_chars=int(cfg.analysis.get("max_scene_chars", 16000)),
        )
        counts = [c for c in people_counts if c is not None]
        if counts:
            annotation["people_count_min"] = min(counts)
            annotation["people_count_max"] = max(counts)
        return annotation

    def _frame_times(self, scenes: list[tuple[float, float]], duration: float) -> list[float]:
        cfg = self.cfg.analysis
        times: set[float] = set()
        for s, e in scenes:
            span = max(e - s, 0.0)
            for k in range(int(cfg["frames_per_scene"])):
                times.add(round(s + span * (k + 1) / (int(cfg["frames_per_scene"]) + 1), 2))
        t = 0.0
        iv = float(cfg["frame_interval_s"])
        while duration and t <= duration:
            times.add(round(t, 2))
            t += iv
        times = sorted(times)
        # 上限：场景极多（快剪）时也要限制总帧数，避免分析过慢
        max_frames = int(cfg.get("max_frames", 200))
        if max_frames > 0 and len(times) > max_frames:
            idxs = {round(i * (len(times) - 1) / (max_frames - 1)) for i in range(max_frames)}
            times = [times[i] for i in sorted(idxs)]
        return times

    def _describe_frame(self, frame_path) -> tuple[str, int | None, str]:
        data = base64.b64encode(Path(frame_path).read_bytes()).decode("ascii")
        resp = self.client.generate(self.cfg.models["vision"], summarize.VISION_PROMPT, images=[data])
        raw = resp.get("response", "") if isinstance(resp, dict) else str(resp)
        desc, n = summarize.parse_vision(raw)
        return desc, n, raw

    def _llm(self, prompt: str) -> str:
        resp = self.client.generate(self.cfg.models["llm"], prompt)
        return resp.get("response", "") if isinstance(resp, dict) else str(resp)

    def _transcribe(self, video: VideoSource, vid: int, run_id: int,
                    audio_path=None) -> tuple[str, list, dict]:
        try:
            if audio_path is None:
                audio_path = media.extract_audio(
                    self._media_src(video),
                    self.cfg.storage_path("frame_cache_dir") / str(vid) / "audio.wav",
                )
            model_path = self.cfg.asr_model_path(self.cfg.models["asr"])
            result = self.transcribe(str(audio_path), str(model_path))
        except Exception as e:
            # 转写失败不阻断整体分析（见计划书 §10）
            self.store.record_error(vid, "asr", traceback.format_exc(), video.file_path)
            return "", [], {"error": f"{type(e).__name__}: {e}"}
        # 兼容返回 (segments, info) 或仅 segments
        if isinstance(result, tuple):
            segments, info = result
        else:
            segments, info = result, {}
        info = dict(info) if isinstance(info, dict) else {}
        info["segments"] = len(segments)
        # 转写成功：清除该视频旧的 asr 失败标记（重新分析后不再标注“音频转换失败”）
        self.store.delete_errors(vid, "asr")
        self.store.save_transcripts([
            {"video_id": vid, "run_id": run_id, "start_sec": s["start"],
             "end_sec": s["end"], "text": s["text"]}
            for s in segments
        ])
        return "\n".join(s["text"] for s in segments), segments, info

    def _save_transcript_files(self, vid: int, original: str, translated: str) -> None:
        """把翻译前后的音频文本临时写到切片目录（分析完随帧缓存一并清理）。"""
        try:
            d = self.cfg.storage_path("frame_cache_dir") / str(vid)
            d.mkdir(parents=True, exist_ok=True)
            (d / "transcript_original.txt").write_text(original, encoding="utf-8")
            (d / "transcript_zh.txt").write_text(translated, encoding="utf-8")
        except Exception:
            pass

    def _write_debug_file(self, video: VideoSource, audio_original: str,
                          audio_zh: str, image_raws: list[str],
                          asr_info: dict | None = None,
                          transcript_summary: str = "") -> None:
        """参考文本测试：在软件目录实时输出 测试{视频名}.txt。"""
        if not self.cfg.output.get("debug_text"):
            return
        try:
            name = video.title or Path(video.file_path).stem
            dest = self.cfg.storage_path("data_dir").parent / f"测试{name}.txt"
            lines = [
                f"音频文本原文：{audio_original if audio_original else '（无内容）'}",
                f"音频文本译文：{audio_zh}",
            ]
            if transcript_summary:
                lines.append(f"音频剧情概括：{transcript_summary}")
            if asr_info and asr_info.get("error"):
                lines.append(f"音频识别信息：错误={asr_info['error']}")
            elif asr_info:
                lang = asr_info.get("language") or "?"
                n = asr_info.get("segments")
                audio_s = asr_info.get("audio_seconds")
                audio_str = f"音频 {audio_s:.0f}秒" if isinstance(audio_s, (int, float)) else "音频 ?秒"
                mb = asr_info.get("model_size_mb")
                mb_str = f"，模型 {mb}MB" if isinstance(mb, (int, float)) else ""
                seg_s = f"{n} 个" if isinstance(n, int) else "?"
                lines.append(f"音频识别信息：语言={lang}，{audio_str}，识别片段={seg_s}{mb_str}")
            else:
                lines.append("音频识别信息：未执行")
            if image_raws:
                lines.append("图片理解文本：")
                for i, t in enumerate(image_raws, 1):
                    lines.append(f"图片{i}：{t}")
            dest.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass

    # ---- 回写 ----
    def _writeback(self, video: VideoSource, vid: int, annotation: dict) -> None:
        _writeback.writeback(self.cfg, self.store, video, annotation, vid)
