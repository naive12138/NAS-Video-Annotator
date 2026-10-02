# -*- coding: utf-8 -*-
"""summarize.py 单元测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from core import summarize  # noqa: E402


class ParseAnnotationTest(unittest.TestCase):
    def test_clean_json(self):
        raw = '{"genre":"悬疑","genre_confidence":0.9,"one_line":"侦探","summary":"悬案","tags":["悬疑","犯罪"]}'
        ann = summarize.parse_annotation(raw)
        self.assertEqual(ann["genre"], "悬疑")
        self.assertEqual(ann["genre_conf"], 0.9)
        self.assertEqual(ann["tags"], ["悬疑", "犯罪"])

    def test_json_in_code_fence(self):
        raw = '```json\n{"genre":"纪录片","one_line":"城市"}\n```'
        ann = summarize.parse_annotation(raw)
        self.assertEqual(ann["genre"], "纪录片")

    def test_json_with_surrounding_text(self):
        raw = '好的，结果如下：{"genre":"家庭","summary":"日常"} 希望有用'
        ann = summarize.parse_annotation(raw)
        self.assertEqual(ann["genre"], "家庭")

    def test_fallback_plain_text(self):
        ann = summarize.parse_annotation("这是一段纯文本剧情")
        self.assertEqual(ann["genre"], "")
        self.assertEqual(ann["one_line"], "这是一段纯文本剧情")

    def test_tags_string(self):
        raw = '{"tags":"悬疑, 犯罪，动作"}'
        ann = summarize.parse_annotation(raw)
        self.assertEqual(ann["tags"], ["悬疑", "犯罪", "动作"])


class PromptTest(unittest.TestCase):
    def test_build_prompt_contains_inputs(self):
        p = summarize.build_summary_prompt(["夜景街头", "室内追逐"], "字幕内容")
        self.assertIn("夜景街头", p)
        self.assertIn("字幕内容", p)
        self.assertIn("genre", p)
        # 格式里不再要求一句话剧情（one_line）
        self.assertNotIn("one_line", p)

    def test_summarize_parses_json(self):
        ann = summarize.summarize(
            ["夜景街头", "室内追逐"], "",
            llm=lambda p: '{"genre":"悬疑","genre_confidence":0.9,'
                           '"summary":"一场紧张的追逐戏","tags":["悬疑","犯罪"]}',
        )
        self.assertEqual(ann["genre"], "悬疑")
        self.assertEqual(ann["summary"], "一场紧张的追逐戏")
        self.assertEqual(ann["one_line"], "")
        self.assertEqual(ann["tags"], ["悬疑", "犯罪"])

    def test_build_prompt_samples_long_scenes(self):
        # 快剪视频场景极多时，场景描述应被均匀抽样，避免提示词过长
        descs = [f"场景描述内容很长的一段话第{i}号" for i in range(500)]
        p = summarize.build_summary_prompt(descs, "", max_scene_chars=500)
        self.assertIn("第0号", p)      # 开头保留
        self.assertIn("第499号", p)    # 结尾保留（均匀抽样）
        self.assertLess(len(p), 2000)  # 总长度受控


class ParseVisionTest(unittest.TestCase):
    def test_clean_json(self):
        desc, people = summarize.parse_vision('{"description": "夜景街头", "people": 2}')
        self.assertEqual(desc, "夜景街头")
        self.assertEqual(people, 2)

    def test_people_as_string(self):
        _, people = summarize.parse_vision('{"description": "x", "people": "3"}')
        self.assertEqual(people, 3)

    def test_fallback_plain_text(self):
        desc, people = summarize.parse_vision("夜景街头")
        self.assertEqual(desc, "夜景街头")
        self.assertIsNone(people)

    def test_json_in_code_fence(self):
        desc, people = summarize.parse_vision('```json\n{"description": "室内", "people": 1}\n```')
        self.assertEqual(desc, "室内")
        self.assertEqual(people, 1)


if __name__ == "__main__":
    unittest.main()
