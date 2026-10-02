# -*- coding: utf-8 -*-
"""SQLite 存储层：所有持久化读写都走这里（见计划书 §4）。

线程安全：写操作用 ``threading.Lock`` 串行；连接 ``check_same_thread=False``。
"""
from __future__ import annotations

import csv
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "db" / "schema.sql"


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    # ---- 连接与建表 ----
    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def init_schema(self) -> None:
        schema = _schema_path().read_text(encoding="utf-8")
        with self._lock:
            self._connect().executescript(schema)
            self._connect().commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ---- 通用写入 ----
    def _insert(self, table: str, data: dict[str, Any]) -> int:
        cols = ", ".join(data.keys())
        marks = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {table} ({cols}) VALUES ({marks})"
        with self._lock:
            cur = self._connect().execute(sql, list(data.values()))
            self._connect().commit()
            return cur.lastrowid

    def _update(self, table: str, row_id: int, data: dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in data)
        sql = f"UPDATE {table} SET {sets} WHERE id = ?"
        with self._lock:
            self._connect().execute(sql, [*data.values(), row_id])
            self._connect().commit()

    def _bulk_insert(self, table: str, rows: Iterable[dict[str, Any]]) -> None:
        rows = list(rows)
        if not rows:
            return
        cols = list(rows[0].keys())
        marks = ", ".join("?" for _ in cols)
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({marks})"
        values = [tuple(r[k] for k in cols) for r in rows]
        with self._lock:
            self._connect().executemany(sql, values)
            self._connect().commit()

    # ---- videos ----
    def upsert_video(self, video: dict[str, Any]) -> int:
        """按 file_path 去重：存在则更新，否则插入。返回 video id。"""
        conn = self._connect()
        file_path = video.get("file_path")
        existing = conn.execute(
            "SELECT id FROM videos WHERE file_path = ?", (file_path,)
        ).fetchone()
        video = dict(video)
        video["updated_at"] = _now()
        if existing:
            vid = existing["id"]
            video.pop("created_at", None)
            self._update("videos", vid, video)
            return vid
        video.setdefault("status", "pending")
        video.setdefault("created_at", _now())
        return self._insert("videos", video)

    def get_video(self, video_id: int) -> dict | None:
        row = self._connect().execute(
            "SELECT * FROM videos WHERE id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_videos(self, status: str | None = None) -> list[dict]:
        if status:
            rows = self._connect().execute(
                "SELECT * FROM videos WHERE status = ?", (status,)
            ).fetchall()
        else:
            rows = self._connect().execute("SELECT * FROM videos").fetchall()
        return [dict(r) for r in rows]

    def set_video_status(self, video_id: int, status: str) -> None:
        self._update("videos", video_id, {"status": status, "updated_at": _now()})

    # ---- analysis_runs ----
    def save_run(self, run: dict[str, Any]) -> int:
        run = dict(run)
        run.setdefault("started_at", _now())
        return self._insert("analysis_runs", run)

    def update_run(self, run_id: int, status: str | None = None,
                   error_msg: str | None = None) -> None:
        data: dict[str, Any] = {"finished_at": _now()}
        if status is not None:
            data["status"] = status
        if error_msg is not None:
            data["error_msg"] = error_msg
        self._update("analysis_runs", run_id, data)

    # ---- 批量写入：scenes / frames / transcripts ----
    def save_scenes(self, scenes: Iterable[dict]) -> None:
        self._bulk_insert("scenes", scenes)

    def save_frames(self, frames: Iterable[dict]) -> None:
        self._bulk_insert("frames", frames)

    def save_transcripts(self, transcripts: Iterable[dict]) -> None:
        self._bulk_insert("transcripts", transcripts)

    # ---- annotations ----
    def save_annotation(self, ann: dict[str, Any]) -> int:
        ann = self._jsonize(dict(ann))
        ann.setdefault("is_edited", 0)
        ann.setdefault("created_at", _now())
        ann.setdefault("updated_at", _now())
        return self._insert("annotations", ann)

    def get_annotation(self, video_id: int) -> dict | None:
        row = self._connect().execute(
            "SELECT * FROM annotations WHERE video_id = ? ORDER BY id DESC LIMIT 1",
            (video_id,),
        ).fetchone()
        return dict(row) if row else None

    def update_annotation(self, ann_id: int, fields: dict[str, Any]) -> None:
        fields = self._jsonize(dict(fields))
        fields["is_edited"] = 1
        fields["updated_at"] = _now()
        self._update("annotations", ann_id, fields)

    def delete_annotation(self, ann_id: int) -> None:
        with self._lock:
            self._connect().execute("DELETE FROM annotations WHERE id = ?", (ann_id,))
            self._connect().commit()

    def delete_all_annotations(self) -> int:
        with self._lock:
            cur = self._connect().execute("DELETE FROM annotations")
            self._connect().commit()
            return cur.rowcount

    @staticmethod
    def _jsonize(data: dict[str, Any]) -> dict[str, Any]:
        return {
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
            for k, v in data.items()
        }

    # ---- 回写记录 ----
    def record_writeback(self, video_id: int, target: str, ok: bool, detail: str) -> int:
        return self._insert("writebacks", {
            "video_id": video_id,
            "target": target,
            "ok": 1 if ok else 0,
            "detail": detail,
            "created_at": _now(),
        })

    def list_writebacks(self, video_id: int) -> list[dict]:
        rows = self._connect().execute(
            "SELECT * FROM writebacks WHERE video_id = ? ORDER BY id DESC", (video_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- 错误记录 ----
    def record_error(self, video_id: int | None, stage: str, reason: str, path: str) -> int:
        return self._insert("errors", {
            "video_id": video_id,
            "stage": stage,
            "reason": reason,
            "path": path,
            "created_at": _now(),
        })

    def list_errors(self) -> list[dict]:
        rows = self._connect().execute(
            "SELECT * FROM errors ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_all_errors(self) -> int:
        with self._lock:
            cur = self._connect().execute("DELETE FROM errors")
            self._connect().commit()
            return cur.rowcount

    def delete_errors(self, video_id: int, stage: str | None = None) -> int:
        """删除指定视频的错误记录；stage 为空则删除该视频全部错误。"""
        sql = "DELETE FROM errors WHERE video_id = ?"
        params: list[Any] = [video_id]
        if stage:
            sql += " AND stage = ?"
            params.append(stage)
        with self._lock:
            cur = self._connect().execute(sql, params)
            self._connect().commit()
            return cur.rowcount

    # ---- 检索（annotations 关联 videos） ----
    def search(
        self,
        query: str | None = None,
        genre: str | None = None,
        source_type: str | None = None,
        people_min: int | None = None,
        people_max: int | None = None,
    ) -> list[dict]:
        sql = (
            "SELECT v.id AS video_id, v.file_path, v.title, v.source_type, "
            "v.jellyfin_item_id, "
            "a.id AS ann_id, a.genre, a.genre_conf, a.people_count_min, a.people_count_max, "
            "a.one_line, a.summary, a.tags, a.language, "
            "EXISTS(SELECT 1 FROM errors e WHERE e.video_id = v.id AND e.stage = 'asr') AS asr_failed "
            "FROM annotations a JOIN videos v ON v.id = a.video_id WHERE 1=1"
        )
        params: list[Any] = []
        if query:
            like = f"%{query}%"
            sql += (" AND (a.one_line LIKE ? OR a.summary LIKE ? OR a.genre LIKE ? "
                     "OR a.tags LIKE ? OR v.title LIKE ?)")
            params += [like, like, like, like, like]
        if genre:
            sql += " AND a.genre = ?"
            params.append(genre)
        if source_type:
            sql += " AND v.source_type = ?"
            params.append(source_type)
        if people_min is not None:
            sql += " AND a.people_count_min >= ?"
            params.append(people_min)
        if people_max is not None:
            sql += " AND a.people_count_max <= ?"
            params.append(people_max)
        sql += " ORDER BY a.id DESC"
        rows = self._connect().execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ---- 导出（annotations 关联 videos） ----
    def export(self, fmt: str, out_path: str | Path) -> Path:
        rows = self.search()
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fmt = fmt.lower()

        def people(r: dict) -> str:
            return f"{r['people_count_min']}~{r['people_count_max']} 人"

        if fmt == "json":
            payload = [
                {
                    "file": r["file_path"],
                    "title": r["title"],
                    "source": r["source_type"],
                    "genre": r["genre"],
                    "people": people(r),
                    "one_line": r["one_line"],
                    "summary": r["summary"],
                    "tags": _parse_tags(r["tags"]),
                    "language": r["language"],
                }
                for r in rows
            ]
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        elif fmt == "csv":
            with out.open("w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["文件名", "题材", "人数", "一句话剧情", "剧情概括", "标签", "来源"])
                for r in rows:
                    w.writerow([
                        r["file_path"], r["genre"], people(r), r["one_line"],
                        r["summary"], r["tags"], r["source_type"],
                    ])
        elif fmt in ("md", "markdown"):
            lines = ["| 文件名 | 题材 | 人数 | 剧情概括 | 来源 |", "|---|---|---|---|---|"]
            for r in rows:
                title = (r["title"] or r["file_path"]).replace("|", "\\|")
                lines.append(
                    f"| {title} | {r['genre']} | {people(r)} | "
                    f"{(r['summary'] or '').replace('|', '\\|')} | {r['source_type']} |"
                )
            out.write_text("\n".join(lines), encoding="utf-8")
        else:
            raise ValueError(f"不支持的导出格式: {fmt}")
        return out


def _parse_tags(tags: str | None) -> list[str]:
    if not tags:
        return []
    try:
        v = json.loads(tags)
        return v if isinstance(v, list) else [str(v)]
    except (json.JSONDecodeError, TypeError):
        return [tags]
