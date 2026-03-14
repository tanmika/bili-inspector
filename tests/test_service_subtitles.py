from pathlib import Path

import pytest

from bili_inspector.errors import CommentModeInvalidError, SubtitleLangNotFoundError, SubtitleTracksUnavailableError
from bili_inspector.service import run_comments, run_subtitles


class DummyBrowser:
    pass


@pytest.fixture
def meta():
    return {
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


@pytest.fixture
def subtitle_tracks():
    return [
        {
            "lan": "ai-zh",
            "lan_doc": "中文",
            "subtitle_url": "https://example.com/ai-zh.json",
        },
        {
            "lan": "ai-en",
            "lan_doc": "English",
            "subtitle_url": "https://example.com/ai-en.json",
        },
    ]



def test_run_subtitles_selects_requested_lang(monkeypatch, tmp_path: Path, meta, subtitle_tracks):
    monkeypatch.setattr(
        "bili_inspector.service.http_get_json",
        lambda url: {"body": [{"from": 0, "to": 1, "content": "hello"}]},
    )
    payload, manifest = run_subtitles(DummyBrowser(), meta, subtitle_tracks, tmp_path, "ai-zh", "main")
    assert payload["subtitles"]["requested_langs"] == ["ai-zh"]
    assert payload["subtitles"]["fetched_langs"] == ["ai-zh"]
    assert payload["subtitles"]["tracks"] == [{"lan": "ai-zh", "lan_doc": "中文"}]
    assert "subtitles/ai-zh.srt" in manifest.files
    assert (tmp_path / "subtitles" / "ai-zh.srt").exists()


@pytest.mark.parametrize(
    ("tracks", "expected_lang"),
    [
        ([{"lan": "ai-zh", "lan_doc": "中文", "subtitle_url": "https://example.com/zh.json"}, {"lan": "ai-en", "lan_doc": "English", "subtitle_url": "https://example.com/en.json"}], "ai-zh"),
        ([{"lan": "en-us", "lan_doc": "English", "subtitle_url": "https://example.com/en.json"}, {"lan": "ja", "lan_doc": "日本語", "subtitle_url": "https://example.com/ja.json"}], "en-us"),
        ([{"lan": "ja-jp", "lan_doc": "日本語", "subtitle_url": "https://example.com/ja.json"}, {"lan": "fr", "lan_doc": "Français", "subtitle_url": "https://example.com/fr.json"}], "ja-jp"),
        ([{"lan": "fr", "lan_doc": "Français", "subtitle_url": "https://example.com/fr.json"}, {"lan": "de", "lan_doc": "Deutsch", "subtitle_url": "https://example.com/de.json"}], "fr"),
    ],
)
def test_run_subtitles_auto_selects_single_track_by_fallback(monkeypatch, tmp_path: Path, meta, tracks, expected_lang):
    monkeypatch.setattr(
        "bili_inspector.service.http_get_json",
        lambda url: {"body": [{"from": 0, "to": 1, "content": url.rsplit("/", 1)[-1]}]},
    )
    payload, manifest = run_subtitles(DummyBrowser(), meta, tracks, tmp_path, None, "main")
    assert payload["subtitles"]["requested_langs"] == []
    assert payload["subtitles"]["fetched_langs"] == [expected_lang]
    assert len(payload["subtitles"]["tracks"]) == 1
    subtitle_outputs = [name for name in manifest.files if name.startswith("subtitles/") and name != "subtitles/tracks.json"]
    assert subtitle_outputs == [
        f"subtitles/{expected_lang}.json",
        f"subtitles/{expected_lang}.txt",
        f"subtitles/{expected_lang}.plain.txt",
        f"subtitles/{expected_lang}.srt",
    ]



def test_run_subtitles_writes_only_selected_track_files(monkeypatch, tmp_path: Path, meta, subtitle_tracks):
    stale_file = tmp_path / "subtitles" / "old-track.srt"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("stale", encoding="utf-8")

    monkeypatch.setattr(
        "bili_inspector.service.http_get_json",
        lambda url: {"body": [{"from": 0, "to": 1, "content": "hello"}]},
    )
    payload, manifest = run_subtitles(DummyBrowser(), meta, subtitle_tracks, tmp_path, None, "main")

    assert payload["subtitles"]["fetched_langs"] == ["ai-zh"]
    assert not stale_file.exists()
    assert manifest.files == [
        "subtitles/tracks.json",
        "subtitles/ai-zh.json",
        "subtitles/ai-zh.txt",
        "subtitles/ai-zh.plain.txt",
        "subtitles/ai-zh.srt",
    ]



def test_run_subtitles_raises_when_lang_missing(meta, subtitle_tracks):
    with pytest.raises(SubtitleLangNotFoundError):
        run_subtitles(DummyBrowser(), meta, subtitle_tracks, None, "ja", "main")



def test_run_subtitles_raises_when_tracks_missing(meta):
    with pytest.raises(SubtitleTracksUnavailableError):
        run_subtitles(DummyBrowser(), meta, [], None, None, "main")



def test_run_comments_rejects_invalid_mode(meta):
    with pytest.raises(CommentModeInvalidError):
        run_comments(DummyBrowser(), meta, None, ["foo"], 20, 10)
