# -*- coding: utf-8 -*-
"""设置页：读写 Config，含“获取模型”与“测试”按钮。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QPushButton, QRadioButton, QStackedWidget,
    QFileDialog, QButtonGroup,
)

from core import ffmpeg as _ffmpeg
from core.config import Config
from core.readiness import check_all
from core.models import asr as _asr
from core.models.ollama_client import OllamaClient
from .util import run_async


class SettingsPage(QWidget):
    _ff_progress = Signal(int, int)  # (done_bytes, total_bytes)
    _asr_progress = Signal(int, int)  # (done_bytes, total_bytes)

    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._build()
        self._ff_progress.connect(self._on_ff_progress_slot)
        self._asr_progress.connect(self._on_asr_progress_slot)
        self.load_from_cfg()

    # ---------- UI ----------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("设置")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        sub = QLabel("模型、路径、回写位置等所有配置都在这里完成")
        sub.setStyleSheet("color: #8a8aa0;")
        root.addWidget(title)
        root.addWidget(sub)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        # 模型服务
        llm = QGroupBox("模型服务")
        lf = QFormLayout(llm)
        lf.setHorizontalSpacing(16); lf.setVerticalSpacing(12)
        self.addr_edit = QLineEdit()
        self.get_btn = QPushButton("获取模型")
        self.get_btn.clicked.connect(self.on_get_models)
        row = QHBoxLayout(); row.setSpacing(8); row.addWidget(self.addr_edit, 1); row.addWidget(self.get_btn)
        lf.addRow("服务地址", row)
        self.timeout_edit = QLineEdit()
        lf.addRow("推理超时(秒)", self.timeout_edit)
        grid.addWidget(llm, 0, 0)

        # 模型
        mod = QGroupBox("模型")
        mf = QFormLayout(mod)
        mf.setHorizontalSpacing(16); mf.setVerticalSpacing(12)
        self.vision_combo = self._combo()
        self.llm_combo = self._combo()
        self.asr_combo = self._combo()
        mf.addRow("视觉模型", self.vision_combo)
        mf.addRow("文本模型", self.llm_combo)
        asr_row = QHBoxLayout(); asr_row.setSpacing(8)
        asr_row.addWidget(self.asr_combo, 1)
        self.asr_download_btn = QPushButton("下载模型")
        self.asr_download_btn.clicked.connect(self.on_asr_download)
        asr_row.addWidget(self.asr_download_btn)
        mf.addRow("ASR 模型", asr_row)
        self.asr_status = QLabel("")
        self.asr_status.setWordWrap(True)
        self.asr_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        mf.addRow("", self.asr_status)
        grid.addWidget(mod, 1, 0)

        # 数据源 · 二选一
        src = QGroupBox("数据源 · 二选一")
        sv = QVBoxLayout(src); sv.setSpacing(12)
        tog = QHBoxLayout(); tog.setSpacing(24)
        self.r_local = QRadioButton("本地路径")
        self.r_jf = QRadioButton("Jellyfin")
        tog.addWidget(self.r_local); tog.addWidget(self.r_jf); tog.addStretch(1)
        sv.addLayout(tog)

        self.src_stack = QStackedWidget()
        lp = QWidget(); lpf = QFormLayout(lp); lpf.setContentsMargins(0, 0, 0, 0)
        lpf.setHorizontalSpacing(16); lpf.setVerticalSpacing(12)
        self.root_edit = QLineEdit()
        browse = QPushButton("浏览")
        browse.clicked.connect(self.on_browse)
        rr = QHBoxLayout(); rr.setSpacing(8); rr.addWidget(self.root_edit, 1); rr.addWidget(browse)
        lpf.addRow("媒体根目录", rr)
        self.r_nfo_first = QRadioButton("优先 NFO")
        self.r_txt_only = QRadioButton("仅 txt")
        self.r_nfo_first.setChecked(True)
        wrad = QHBoxLayout(); wrad.setSpacing(20)
        wrad.addWidget(self.r_nfo_first); wrad.addWidget(self.r_txt_only); wrad.addStretch(1)
        lpf.addRow("回写方式", wrad)
        self.txt_name = QLineEdit()
        self.txt_append = QRadioButton("继续写入")
        self.txt_new = QRadioButton("新建(1)")
        self.txt_new.setChecked(True)
        rad = QHBoxLayout(); rad.setSpacing(20)
        rad.addWidget(self.txt_append); rad.addWidget(self.txt_new); rad.addStretch(1)
        lpf.addRow("txt 默认文件名", self.txt_name)
        lpf.addRow("txt 已存在时", rad)
        self.src_stack.addWidget(lp)

        # 分组：避免同父控件下所有单选互斥
        self._write_mode_group = QButtonGroup(self)
        self._write_mode_group.addButton(self.r_nfo_first)
        self._write_mode_group.addButton(self.r_txt_only)
        self._txt_mode_group = QButtonGroup(self)
        self._txt_mode_group.addButton(self.txt_append)
        self._txt_mode_group.addButton(self.txt_new)

        jp = QWidget(); jpf = QFormLayout(jp); jpf.setContentsMargins(0, 0, 0, 0)
        jpf.setHorizontalSpacing(16); jpf.setVerticalSpacing(12)
        self.jf_url = QLineEdit()
        self.jf_key = QLineEdit()
        self.jf_key.setEchoMode(QLineEdit.Password)
        jpf.addRow("服务器地址", self.jf_url)
        jpf.addRow("API Key", self.jf_key)
        self.src_stack.addWidget(jp)
        sv.addWidget(self.src_stack)
        self.r_local.toggled.connect(lambda on: self.src_stack.setCurrentIndex(0) if on else None)
        self.r_jf.toggled.connect(lambda on: self.src_stack.setCurrentIndex(1) if on else None)
        grid.addWidget(src, 0, 1, 2, 1)

        # 分析参数
        ap = QGroupBox("分析参数")
        ag = QGridLayout(ap); ag.setHorizontalSpacing(16)
        self.param_edits = {}
        for i, key in enumerate(["frame_interval_s", "frames_per_scene", "scene_threshold", "max_frames"]):
            lab = QLabel({"frame_interval_s": "抽帧间隔(秒)", "frames_per_scene": "每场景帧数",
                          "scene_threshold": "场景阈值", "max_frames": "最大帧数"}[key])
            ed = QLineEdit()
            self.param_edits[key] = ed
            box = QVBoxLayout(); box.setSpacing(6); box.addWidget(lab); box.addWidget(ed)
            ag.addLayout(box, 0, i)
        grid.addWidget(ap, 2, 0, 1, 2)

        # FFmpeg 状态 + 一键下载
        ffg = QGroupBox("FFmpeg（抽帧 / 音轨 / 场景切分所需）")
        ffv = QVBoxLayout(ffg); ffv.setSpacing(10)
        self.ffmpeg_status = QLabel("")
        self.ffmpeg_status.setWordWrap(True)
        self.ffmpeg_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        ffv.addWidget(self.ffmpeg_status)
        ffb = QHBoxLayout(); ffb.setSpacing(10)
        self.ff_check_btn = QPushButton("重新检测")
        self.ff_check_btn.clicked.connect(self.refresh_ffmpeg_status)
        self.ff_download_btn = QPushButton("一键下载 FFmpeg")
        self.ff_download_btn.clicked.connect(self.on_ff_download)
        ffb.addWidget(self.ff_check_btn)
        ffb.addWidget(self.ff_download_btn)
        ffb.addStretch(1)
        ffv.addLayout(ffb)
        grid.addWidget(ffg, 3, 0, 1, 2)

        root.addLayout(grid, 1)

        # 底部
        bottom = QHBoxLayout(); bottom.setSpacing(12)
        self.test_btn = QPushButton("测试")
        self.test_btn.setObjectName("green")
        self.test_btn.clicked.connect(self.on_test)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bottom.addWidget(self.test_btn)
        bottom.addWidget(self.status_label, 1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.load_from_cfg)
        self.save_btn = QPushButton("保存")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self.save)
        bottom.addWidget(cancel)
        bottom.addWidget(self.save_btn)
        root.addLayout(bottom)

    @staticmethod
    def _combo() -> QComboBox:
        c = QComboBox()
        c.setEditable(True)
        return c

    # ---------- 读写配置 ----------
    def load_from_cfg(self):
        c = self.cfg
        self.addr_edit.setText(c.ollama["base_url"])
        self.vision_combo.setCurrentText(c.models["vision"])
        self.llm_combo.setCurrentText(c.models["llm"])
        self.asr_combo.setCurrentText(c.models["asr"])
        self.txt_name.setText(c.output["txt_name"])
        (self.txt_append if c.output["txt_mode"] == "append" else self.txt_new).setChecked(True)
        if c.jellyfin.get("enabled") or c.local_paths.get("roots"):
            self.r_jf.setChecked(bool(c.jellyfin.get("enabled")))
            self.r_local.setChecked(not c.jellyfin.get("enabled"))
        else:
            self.r_local.setChecked(True)
        self.root_edit.setText(c.local_paths["roots"][0] if c.local_paths["roots"] else "")
        (self.r_nfo_first if c.output.get("local_mode", "nfo_first") == "nfo_first" else self.r_txt_only).setChecked(True)
        self.jf_url.setText(c.jellyfin["base_url"])
        self.jf_key.setText(c.jellyfin["api_key"])
        self.timeout_edit.setText(str(c.ollama.get("generate_timeout_s", 600)))
        for key, ed in self.param_edits.items():
            ed.setText(str(c.analysis[key]))
        self.status_label.setText("")
        self.refresh_ffmpeg_status()
        self.refresh_asr_status()

    def save(self) -> None:
        c = self.cfg
        c._data["ollama"]["base_url"] = self.addr_edit.text().strip()
        try:
            c._data["ollama"]["generate_timeout_s"] = int(float(self.timeout_edit.text()))
        except ValueError:
            pass
        c._data["models"]["vision"] = self.vision_combo.currentText().strip()
        c._data["models"]["llm"] = self.llm_combo.currentText().strip()
        c._data["models"]["asr"] = self.asr_combo.currentText().strip()
        c._data["output"]["txt_name"] = self.txt_name.text().strip() or "简介{filename}.txt"
        c._data["output"]["txt_mode"] = "append" if self.txt_append.isChecked() else "new"
        c._data["output"]["local_mode"] = "nfo_first" if self.r_nfo_first.isChecked() else "txt_only"
        c._data["local_paths"]["roots"] = [self.root_edit.text().strip()] if self.root_edit.text().strip() else []
        c._data["jellyfin"]["enabled"] = self.r_jf.isChecked()
        c._data["jellyfin"]["base_url"] = self.jf_url.text().strip()
        c._data["jellyfin"]["api_key"] = self.jf_key.text().strip()
        for key, ed in self.param_edits.items():
            try:
                c._data["analysis"][key] = float(ed.text())
            except ValueError:
                pass
        c.save()
        self.status_label.setText("已保存")

    # ---------- 动作 ----------
    def on_browse(self):
        d = QFileDialog.getExistingDirectory(self, "选择媒体根目录", self.root_edit.text())
        if d:
            self.root_edit.setText(d)

    def on_get_models(self):
        url = self.addr_edit.text().strip()
        self.status_label.setText("正在获取模型…")

        def fn():
            return OllamaClient(url).model_names()

        def done(names, err):
            if err:
                self.status_label.setText(f"获取模型失败：{err}")
                return
            if not names:
                self.status_label.setText("未获取到任何模型（模型服务可能未启动或无模型）")
                return
            self._fill_models(names)
            self.status_label.setText(f"已获取 {len(names)} 个模型")

        self._worker = run_async(fn, done)

    def _fill_models(self, names):
        for combo in (self.vision_combo, self.llm_combo):
            prev = combo.currentText()
            combo.clear()
            combo.addItems(names)
            if names:
                if prev and prev in names:
                    combo.setCurrentText(prev)
                else:
                    combo.setCurrentIndex(0)

    def on_test(self):
        self.status_label.setText("正在检测…")
        cfg = self.cfg
        # 用当前界面值做检测，避免必须先保存
        cfg._data["ollama"]["base_url"] = self.addr_edit.text().strip()
        cfg._data["models"]["vision"] = self.vision_combo.currentText().strip()
        cfg._data["models"]["llm"] = self.llm_combo.currentText().strip()
        cfg._data["models"]["asr"] = self.asr_combo.currentText().strip()

        def fn():
            return check_all(cfg)

        def done(results, err):
            if err:
                self.status_label.setText(f"检测出错：{err}")
                return
            lines = []
            for r in results:
                mark = "✓" if r["ready"] else "✗"
                lines.append(f"{mark} {r['item']}" + ("" if r["ready"] else f" —— {r['reason']}"))
            self.status_label.setText("\n".join(lines))

        self._worker = run_async(fn, done)

    # ---------- FFmpeg ----------
    def refresh_ffmpeg_status(self):
        st = _ffmpeg.status(self.cfg)
        if st["ok"]:
            self.ffmpeg_status.setText(
                "✓ FFmpeg 已就绪\nffmpeg: " + (st["ffmpeg"] or "") +
                "\nffprobe: " + (st["ffprobe"] or "")
            )
        else:
            self.ffmpeg_status.setText(
                "✗ 未找到 ffmpeg/ffprobe，分析将无法进行。\n"
                "请点击下方“一键下载 FFmpeg”（约 100MB，自动解压到本机）。\n"
                "ffmpeg: " + (st["ffmpeg"] or "未找到") +
                "\nffprobe: " + (st["ffprobe"] or "未找到")
            )

    def on_ff_download(self):
        self.ffmpeg_status.setText("正在下载 FFmpeg…（约 100MB，请稍候）")

        def fn():
            _ffmpeg.ensure_ffmpeg(self.cfg, on_progress=lambda d, t: self._ff_progress.emit(d, t))
            return _ffmpeg.status(self.cfg)

        def done(st, err):
            if err:
                self.ffmpeg_status.setText(
                    "下载失败：" + str(err) +
                    "\n可手动下载 ffmpeg/ffprobe 并放到 exe 同目录或加入 PATH"
                )
                return
            self.refresh_ffmpeg_status()

        self._worker = run_async(fn, done)

    def _on_ff_progress_slot(self, done_bytes, total_bytes):
        pct = int(done_bytes / total_bytes * 100) if total_bytes else 0
        self.ffmpeg_status.setText(
            f"正在下载 FFmpeg… {pct}%"
            f"（{done_bytes // (1024 * 1024)} / {total_bytes // (1024 * 1024)} MB）"
        )

    # ---------- ASR 模型下载 ----------
    def refresh_asr_status(self):
        name = self.asr_combo.currentText().strip()
        if not name:
            self.asr_status.setText("请先填写 ASR 模型名（如 small）")
            return
        if _asr.is_model_ready(self.cfg, name):
            self.asr_status.setText(f"✓ ASR 模型 {name} 已就绪\n{_asr.model_dir(self.cfg, name)}")
        else:
            self.asr_status.setText(f"✗ ASR 模型 {name} 未下载，请点击“下载模型”（国内镜像源）")

    def on_asr_download(self):
        name = self.asr_combo.currentText().strip()
        if not name:
            self.asr_status.setText("请先填写 ASR 模型名（如 small）")
            return
        self.asr_status.setText(f"正在下载 ASR 模型 {name}…（首次约几百 MB，请稍候）")

        def fn():
            _asr.download_model(
                self.cfg, name,
                on_progress=lambda d, t: self._asr_progress.emit(d, t),
            )
            return name

        def done(_name, err):
            if err:
                self.asr_status.setText(
                    f"下载失败：{err}\n"
                    f"可稍后重试，或手动下载后放入 {_asr.model_dir(self.cfg, name)}"
                )
                return
            self.refresh_asr_status()

        self._worker = run_async(fn, done)

    def _on_asr_progress_slot(self, done_bytes, total_bytes):
        pct = int(done_bytes / total_bytes * 100) if total_bytes else 0
        self.asr_status.setText(
            f"正在下载 ASR 模型… {pct}%"
            f"（{done_bytes // (1024 * 1024)} / {total_bytes // (1024 * 1024)} MB）"
        )
