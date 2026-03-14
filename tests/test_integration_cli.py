import shutil
from pathlib import Path

from bili_inspector.cli import build_parser, default_output_dir, default_search_output_dir, run_command


class FakeBrowser:
    def __init__(self, session_name):
        self.session_name = session_name



def fake_meta(bvid: str):
    return {
        "bvid": bvid,
        "aid": "115865802510979",
        "cid": "35287862688",
        "title": "demo",
        "owner_name": "owner",
        "pubdate": "2026-01-09 23:19:59",
        "reply_count": 112,
        "url": f"https://www.bilibili.com/video/{bvid}/",
        "desc": "desc",
    }



def test_run_command_meta_uses_fixed_repo_output_dir(monkeypatch):
    bvid = "BV1aurMBCEkE"
    out_dir = default_output_dir(bvid)
    shutil.rmtree(out_dir, ignore_errors=True)

    monkeypatch.setattr("bili_inspector.cli.BrowserClient", FakeBrowser)
    monkeypatch.setattr(
        "bili_inspector.cli.resolve_video",
        lambda browser, actual_bvid: (fake_meta(actual_bvid), [{"lan": "ai-zh", "lan_doc": "中文"}]),
    )

    parser = build_parser()
    args = parser.parse_args(["meta", bvid, "--json"])
    envelope = run_command(args).to_dict()

    try:
        assert envelope["ok"] is True
        assert envelope["command"] == "meta"
        assert envelope["data"]["video"]["bvid"] == bvid
        assert envelope["data"]["availability"]["subtitles"]["langs"] == ["ai-zh"]
        assert envelope["artifacts"]["output_dir"] == str(out_dir)
        assert envelope["artifacts"]["files"] == ["README.md", "meta.json"]
        assert envelope["warnings"] == []
        assert (out_dir / "meta.json").exists()
        assert (out_dir / "README.md").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)



def test_run_command_subtitles_rebuilds_only_subtitles_partition(monkeypatch):
    bvid = "BV1aurMBCEkF"
    out_dir = default_output_dir(bvid)
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text("{}", encoding="utf-8")
    (out_dir / "stale.txt").write_text("old", encoding="utf-8")
    comments_dir = out_dir / "comments"
    comments_dir.mkdir(parents=True, exist_ok=True)
    (comments_dir / "hot.md").write_text("keep", encoding="utf-8")
    subtitles_dir = out_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    (subtitles_dir / "old-track.srt").write_text("old sub", encoding="utf-8")

    monkeypatch.setattr("bili_inspector.cli.BrowserClient", FakeBrowser)
    monkeypatch.setattr(
        "bili_inspector.cli.resolve_video",
        lambda browser, actual_bvid: (
            fake_meta(actual_bvid),
            [
                {"lan": "ai-en", "lan_doc": "English", "subtitle_url": "https://example.com/ai-en.json"},
                {"lan": "ja", "lan_doc": "日本語", "subtitle_url": "https://example.com/ja.json"},
            ],
        ),
    )
    monkeypatch.setattr(
        "bili_inspector.service.http_get_json",
        lambda url: {"body": [{"from": 0, "to": 1, "content": "hello"}]},
    )

    parser = build_parser()
    args = parser.parse_args(["subtitles", bvid, "--json"])
    envelope = run_command(args).to_dict()

    try:
        assert envelope["artifacts"]["output_dir"] == str(out_dir)
        assert envelope["data"]["subtitles"]["fetched_langs"] == ["ai-en"]
        assert envelope["warnings"] == []
        assert not (out_dir / "stale.txt").exists()
        assert (out_dir / "meta.json").exists()
        assert (out_dir / "comments" / "hot.md").exists()
        assert not (out_dir / "subtitles" / "old-track.srt").exists()
        assert envelope["artifacts"]["files"] == [
            "README.md",
            "comments/hot.md",
            "meta.json",
            "subtitles/ai-en.json",
            "subtitles/ai-en.plain.txt",
            "subtitles/ai-en.srt",
            "subtitles/ai-en.txt",
            "subtitles/tracks.json",
        ]
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)



def test_run_command_stepwise_fetch_accumulates_full_snapshot(monkeypatch):
    bvid = "BV1aurMBCEkG"
    out_dir = default_output_dir(bvid)
    shutil.rmtree(out_dir, ignore_errors=True)

    monkeypatch.setattr("bili_inspector.cli.BrowserClient", FakeBrowser)
    monkeypatch.setattr(
        "bili_inspector.cli.resolve_video",
        lambda browser, actual_bvid: (
            fake_meta(actual_bvid),
            [{"lan": "ai-zh", "lan_doc": "中文", "subtitle_url": "https://example.com/ai-zh.json"}],
        ),
    )
    monkeypatch.setattr(
        "bili_inspector.service.http_get_json",
        lambda url: {"body": [{"from": 0, "to": 1, "content": "subtitle"}]},
    )
    monkeypatch.setattr(
        "bili_inspector.service.fetch_comments",
        lambda browser, aid, mode, limit, subreply_limit: [
            {"rpid": "1", "user": "u", "like": 1, "reply_count": 0, "message": f"m-{mode}"}
        ],
    )

    parser = build_parser()
    meta_envelope = run_command(parser.parse_args(["meta", bvid, "--json"])).to_dict()
    subtitles_envelope = run_command(parser.parse_args(["subtitles", bvid, "--json"])).to_dict()
    comments_envelope = run_command(parser.parse_args(["comments", bvid, "--json"])).to_dict()

    try:
        disk_files = sorted(str(path.relative_to(out_dir)) for path in out_dir.rglob("*") if path.is_file())
        assert meta_envelope["artifacts"]["files"] == ["README.md", "meta.json"]
        assert subtitles_envelope["artifacts"]["files"] == [
            "README.md",
            "meta.json",
            "subtitles/ai-zh.json",
            "subtitles/ai-zh.plain.txt",
            "subtitles/ai-zh.srt",
            "subtitles/ai-zh.txt",
            "subtitles/tracks.json",
        ]
        assert comments_envelope["artifacts"]["files"] == disk_files
        assert disk_files == [
            "README.md",
            "comments/hot.json",
            "comments/hot.md",
            "comments/latest.json",
            "comments/latest.md",
            "meta.json",
            "subtitles/ai-zh.json",
            "subtitles/ai-zh.plain.txt",
            "subtitles/ai-zh.srt",
            "subtitles/ai-zh.txt",
            "subtitles/tracks.json",
        ]
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)



def test_run_command_inspect_writes_readme_and_matching_artifacts(monkeypatch):
    bvid = "BV1aurMBCEg1"
    out_dir = default_output_dir(bvid)
    shutil.rmtree(out_dir, ignore_errors=True)

    monkeypatch.setattr("bili_inspector.cli.BrowserClient", FakeBrowser)
    monkeypatch.setattr(
        "bili_inspector.cli.resolve_video",
        lambda browser, actual_bvid: (
            fake_meta(actual_bvid),
            [
                {"lan": "fr", "lan_doc": "Français", "subtitle_url": "https://example.com/fr.json"},
                {"lan": "ja", "lan_doc": "日本語", "subtitle_url": "https://example.com/ja.json"},
            ],
        ),
    )
    monkeypatch.setattr(
        "bili_inspector.service.http_get_json",
        lambda url: {"body": [{"from": 0, "to": 1, "content": "subtitle"}]},
    )
    monkeypatch.setattr(
        "bili_inspector.service.fetch_comments",
        lambda browser, aid, mode, limit, subreply_limit: [
            {"rpid": "1", "user": "u", "like": 1, "reply_count": 0, "message": f"m-{mode}"}
        ],
    )

    parser = build_parser()
    args = parser.parse_args(["inspect", bvid, "--json"])
    envelope = run_command(args).to_dict()

    try:
        readme = (out_dir / "README.md").read_text(encoding="utf-8")
        disk_files = sorted(str(path.relative_to(out_dir)) for path in out_dir.rglob("*") if path.is_file())

        assert envelope["artifacts"]["output_dir"] == str(out_dir)
        assert envelope["data"]["subtitles"]["fetched_langs"] == ["ja"]
        assert envelope["warnings"] == []
        assert "## 字幕文件说明" in readme
        assert "`*.plain.txt`：纯文本，最适合 AI 直接阅读、总结、抽取主题。" in readme
        assert "## 评论文件说明" in readme
        assert "`comments/hot.json` / `comments/latest.json`：结构化数据，适合 AI 程序化解析。" in readme
        assert "- `ja` / 日本語" in readme
        assert "- `fr` / Français" not in readme
        assert "- `subtitles/ja.plain.txt`" in readme
        assert "- `comments/hot.json`" in readme
        assert sorted(envelope["artifacts"]["files"]) == disk_files
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)



def test_run_command_search_returns_compact_results_without_artifacts(monkeypatch):
    class SearchBrowser:
        def __init__(self, session_name):
            self.session_name = session_name

        def open(self, url):
            self.url = url

        def fetch_json(self, url):
            return {
                "code": 0,
                "data": {
                    "numResults": 1234,
                    "numPages": 62,
                    "result": [
                        {"title": "<em class=\"keyword\">原神</em> 启动器", "bvid": "BV1aaaaaa111", "pubdate": 1709286600, "play": "12.3万"},
                        {"title": "第二条", "bvid": "BV1bbbbbb222", "pubdate": 1709373000, "play": "3.4万"},
                    ],
                },
            }

    monkeypatch.setattr("bili_inspector.cli.BrowserClient", SearchBrowser)

    parser = build_parser()
    args = parser.parse_args(["search", "原神", "启动器", "--json"])
    envelope = run_command(args).to_dict()

    assert envelope == {
        "ok": True,
        "schema_version": "1",
        "command": "search",
        "input": {"keyword": "原神 启动器", "page": 1, "limit": 10, "session_name": "main"},
        "data": {
            "search": {
                "keyword": "原神 启动器",
                "page": 1,
                "limit": 10,
                "total": 1234,
                "pages": 62,
                "returned": 2,
                "results": [
                    {"title": "原神 启动器", "bvid": "BV1aaaaaa111", "pubdate": "2024-03-01 17:50:00", "play": "12.3万"},
                    {"title": "第二条", "bvid": "BV1bbbbbb222", "pubdate": "2024-03-02 17:50:00", "play": "3.4万"},
                ],
            }
        },
        "warnings": [],
    }



def test_run_command_search_save_raw_writes_artifact(monkeypatch):
    class SearchBrowser:
        def __init__(self, session_name):
            self.session_name = session_name

        def open(self, url):
            self.url = url

        def fetch_json(self, url):
            return {
                "code": 0,
                "data": {
                    "numResults": 1234,
                    "numPages": 62,
                    "result": [
                        {"title": "<em class=\"keyword\">原神</em> 启动器", "bvid": "BV1aaaaaa111", "pubdate": 1709286600, "play": "12.3万"},
                    ],
                },
            }

    out_dir = default_search_output_dir("原神 启动器")
    shutil.rmtree(out_dir, ignore_errors=True)
    monkeypatch.setattr("bili_inspector.cli.BrowserClient", SearchBrowser)

    parser = build_parser()
    args = parser.parse_args(["search", "原神", "启动器", "--json", "--save-raw"])
    envelope = run_command(args).to_dict()

    try:
        assert envelope["artifacts"] == {"output_dir": str(out_dir), "files": ["raw.json"]}
        assert (out_dir / "raw.json").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
