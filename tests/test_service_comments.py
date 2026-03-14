from pathlib import Path

from bili_inspector.service import run_comments


class FakeBrowser:
    def __init__(self):
        self.calls = []



def test_run_comments_writes_artifacts(monkeypatch, tmp_path: Path):
    meta = {
        "bvid": "BV1xxxxxxxxx",
        "aid": "123456789012345",
        "cid": "12345678901",
        "title": "demo",
        "owner_name": "owner",
        "pubdate": "2025-01-01 12:00:00",
        "reply_count": 100,
        "url": "https://www.bilibili.com/video/BV1xxxxxxxxx/",
        "desc": "desc",
    }
    monkeypatch.setattr(
        "bili_inspector.service.fetch_comments",
        lambda browser, aid, mode, limit, subreply_limit: [
            {"rpid": "1", "user": "u", "like": 1, "reply_count": 0, "message": "m"}
            for _ in range(limit)
        ],
    )
    payload, manifest = run_comments(FakeBrowser(), meta, tmp_path, ["hot", "latest"], 2, 10)
    assert payload["comments"]["modes"]["hot"]["requested_limit"] == 2
    assert payload["comments"]["modes"]["hot"]["fetched_roots"] == 2
    assert payload["comments"]["modes"]["hot"]["truncated"] is True
    assert "comments/hot.json" in manifest.files
    assert "comments/latest.md" in manifest.files
    assert (tmp_path / "comments" / "hot.json").exists()



def test_run_comments_marks_all_as_not_truncated(monkeypatch):
    meta = {
        "bvid": "BV1xxxxxxxxx",
        "aid": "123456789012345",
        "cid": "12345678901",
        "title": "demo",
        "owner_name": "owner",
        "pubdate": "2025-01-01 12:00:00",
        "reply_count": 100,
        "url": "https://www.bilibili.com/video/BV1xxxxxxxxx/",
        "desc": "desc",
    }
    monkeypatch.setattr(
        "bili_inspector.service.fetch_comments",
        lambda browser, aid, mode, limit, subreply_limit: [
            {"rpid": "1", "user": "u", "like": 1, "reply_count": 0, "message": "m"}
        ],
    )
    payload, manifest = run_comments(FakeBrowser(), meta, None, ["hot"], None, None)
    assert payload["comments"]["modes"]["hot"]["requested_limit"] == "all"
    assert payload["comments"]["modes"]["hot"]["subreply_limit"] == "all"
    assert payload["comments"]["modes"]["hot"]["truncated"] is False
    assert manifest.files == []
