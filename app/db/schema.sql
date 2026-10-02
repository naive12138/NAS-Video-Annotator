-- NAS 视频内容分析与标注系统 —— SQLite 表结构（见计划书 §4）

CREATE TABLE IF NOT EXISTS videos (
  id               INTEGER PRIMARY KEY,
  source_type      TEXT NOT NULL,           -- 'local' | 'jellyfin'
  jellyfin_item_id TEXT,
  file_path        TEXT NOT NULL,           -- 本地可访问路径（UNC 或盘符）
  title            TEXT,
  duration_sec     REAL,
  width            INTEGER,
  height           INTEGER,
  fps              REAL,
  codec            TEXT,
  size_bytes       INTEGER,
  status           TEXT DEFAULT 'pending',  -- pending/processing/done/failed
  created_at       TEXT,
  updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS analysis_runs (
  id           INTEGER PRIMARY KEY,
  video_id     INTEGER REFERENCES videos(id),
  status       TEXT,
  model_name   TEXT,
  config_json  TEXT,
  error_msg    TEXT,
  started_at   TEXT,
  finished_at  TEXT
);

CREATE TABLE IF NOT EXISTS scenes (
  id          INTEGER PRIMARY KEY,
  video_id    INTEGER REFERENCES videos(id),
  run_id      INTEGER REFERENCES analysis_runs(id),
  scene_index INTEGER,
  start_sec   REAL,
  end_sec     REAL,
  description TEXT,
  representative_frame_path TEXT
);

CREATE TABLE IF NOT EXISTS frames (
  id           INTEGER PRIMARY KEY,
  video_id     INTEGER,
  scene_id     INTEGER,
  time_sec     REAL,
  image_path   TEXT,
  description  TEXT,
  people_count INTEGER,
  people_conf  REAL
);

CREATE TABLE IF NOT EXISTS transcripts (
  id        INTEGER PRIMARY KEY,
  video_id  INTEGER,
  run_id    INTEGER,
  start_sec REAL,
  end_sec   REAL,
  text      TEXT,
  speaker   TEXT
);

CREATE TABLE IF NOT EXISTS annotations (
  id               INTEGER PRIMARY KEY,
  video_id         INTEGER,
  run_id           INTEGER,
  genre            TEXT,
  genre_conf       REAL,
  people_count_min INTEGER,
  people_count_max INTEGER,
  one_line         TEXT,
  summary          TEXT,
  tags             TEXT,                   -- JSON 数组字符串
  language         TEXT,
  is_edited        INTEGER DEFAULT 0,
  created_at       TEXT,
  updated_at       TEXT
);

-- 回写记录：成功/失败都记，供界面展示与去重
CREATE TABLE IF NOT EXISTS writebacks (
  id         INTEGER PRIMARY KEY,
  video_id   INTEGER,
  target     TEXT,                         -- 'txt' | 'jellyfin' | 'nfo'
  ok         INTEGER,
  detail     TEXT,
  created_at TEXT
);

-- 错误表：供软件“错误框”展示
CREATE TABLE IF NOT EXISTS errors (
  id         INTEGER PRIMARY KEY,
  video_id   INTEGER,
  stage      TEXT,                         -- 如 'writeback' / 'analyze'
  reason     TEXT,
  path       TEXT,
  created_at TEXT
);
