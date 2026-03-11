from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .browser import BrowserClient
from .errors import (
    BilibiliApiFailedError,
    CommentModeInvalidError,
    CommentsUnavailableError,
    PlayerInfoFetchFailedError,
    SubtitleLangNotFoundError,
    SubtitleTracksUnavailableError,
    VideoStateMissingError,
)
from .exporters import (
    comments_to_markdown,
    render_subtitle_plain,
    render_subtitle_srt,
    render_subtitle_txt,
    summary_markdown,
    write_json,
    write_text,
)
from .models import ArtifactManifest, SubtitleTrackSummary, VideoMeta, to_plain_data

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.bilibili.com/",
}
WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]
BVID_PATTERN = re.compile(r"^BV[0-9A-Za-z]{10}$")
MODE_MAP = {"hot": 3, "latest": 2}
LimitValue = int | None
SEARCH_TITLE_TAG_RE = re.compile(r"<[^>]+>")



def parse_limit(raw: str) -> LimitValue:
    value = raw.strip().lower()
    if value in {"all", "-1", "full"}:
        return None
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("数量必须为正整数，或使用 all")
    return number



def parse_search_page(raw: str) -> int:
    value = int(raw.strip())
    if value <= 0:
        raise argparse.ArgumentTypeError("页码必须为正整数")
    return value



def parse_search_limit(raw: str) -> int:
    value = int(raw.strip())
    if value <= 0:
        raise argparse.ArgumentTypeError("limit 必须为正整数")
    if value > 20:
        raise argparse.ArgumentTypeError("limit 不能超过 20")
    return value



def parse_bvid(raw: str) -> str:
    candidate = raw.strip()
    if not BVID_PATTERN.fullmatch(candidate):
        from .errors import InvalidBvidError

        raise InvalidBvidError(raw)
    return candidate



def timestamp_to_iso(unix_timestamp: int) -> str:
    if not unix_timestamp:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(unix_timestamp))



def http_get(url: str, timeout: int = 20) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = Request(url, headers=DEFAULT_HEADERS)
            with urlopen(request, timeout=timeout) as response:
                data = response.read()
                encoding = (response.headers.get("Content-Encoding") or "").lower()
                if encoding == "gzip" or data[:2] == b"\x1f\x8b":
                    data = gzip.decompress(data)
                charset = response.headers.get_content_charset() or "utf-8"
                return data.decode(charset, errors="replace")
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(1 + attempt)
    raise BilibiliApiFailedError("http_get", str(last_error or url))



def http_get_json(url: str, timeout: int = 20) -> Any:
    return json.loads(http_get(url, timeout=timeout))



def absolute_subtitle_url(url: str) -> str:
    return f"https:{url}" if url.startswith("//") else url



def get_wbi_mixin_key(nav_json: dict[str, Any]) -> str:
    img_url = nav_json["data"]["wbi_img"]["img_url"]
    sub_url = nav_json["data"]["wbi_img"]["sub_url"]
    img_key = img_url.rsplit("/", 1)[-1].split(".")[0]
    sub_key = sub_url.rsplit("/", 1)[-1].split(".")[0]
    orig = img_key + sub_key
    return "".join(orig[index] for index in WBI_MIXIN_KEY_ENC_TAB)[:32]



def sign_wbi_params(params: dict[str, Any], mixin_key: str) -> str:
    sanitized = {key: re.sub(r"[!'()*]", "", str(value)) for key, value in params.items()}
    query = urlencode(sorted(sanitized.items()))
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return f"{query}&w_rid={w_rid}"



def simplify_reply(reply: dict[str, Any]) -> dict[str, Any]:
    member = reply.get("member") or {}
    content = reply.get("content") or {}
    return {
        "rpid": reply.get("rpid_str") or str(reply.get("rpid") or ""),
        "user": member.get("uname") or "",
        "like": reply.get("like") or 0,
        "reply_count": reply.get("rcount") or 0,
        "message": content.get("message") or "",
    }



def build_search_page_url(keyword: str) -> str:
    return f"https://search.bilibili.com/all?keyword={quote(keyword)}"



def build_search_api_url(keyword: str, page: int) -> str:
    query = urlencode({"search_type": "video", "keyword": keyword, "page": page})
    return f"https://api.bilibili.com/x/web-interface/search/type?{query}"



def strip_search_title_html(value: str) -> str:
    return html.unescape(SEARCH_TITLE_TAG_RE.sub("", value or "")).strip()



def normalize_search_result(item: dict[str, Any]) -> dict[str, str]:
    bvid = str(item.get("bvid") or "").strip()
    return {
        "title": strip_search_title_html(str(item.get("title") or "")),
        "bvid": bvid,
        "pubdate": timestamp_to_iso(int(item.get("pubdate") or 0)),
        "play": str(item.get("play") or ""),
    }



def write_search_raw_artifact(output_dir: Path, raw_payload: dict[str, Any]) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "raw.json", raw_payload)
    return list_artifact_files(output_dir)



def run_search(
    browser: BrowserClient,
    keyword: str,
    page: int,
    limit: int,
    save_raw: bool = False,
    out_dir: Path | None = None,
) -> tuple[dict[str, Any], ArtifactManifest | None]:
    browser.open(build_search_page_url(keyword))
    payload = browser.fetch_json(build_search_api_url(keyword, page))
    if int(payload.get("code", -1)) != 0:
        raise BilibiliApiFailedError("search.fetch_results", str(payload)[:300])

    data = payload.get("data") or {}
    raw_results = data.get("result") or []
    filtered = [item for item in raw_results if str(item.get("bvid") or "").strip()]
    results = [normalize_search_result(item) for item in filtered[:limit]]

    search_payload = {
        "search": {
            "keyword": keyword,
            "page": page,
            "limit": limit,
            "total": int(data.get("numResults") or 0),
            "pages": int(data.get("numPages") or 0),
            "returned": len(results),
            "results": results,
        }
    }

    if not save_raw or out_dir is None:
        return search_payload, None

    raw_artifact = {
        "keyword": keyword,
        "page": page,
        "limit": limit,
        "total": int(data.get("numResults") or 0),
        "pages": int(data.get("numPages") or 0),
        "result": raw_results,
    }
    files = write_search_raw_artifact(out_dir, raw_artifact)
    manifest = ArtifactManifest(output_dir=str(out_dir), files=files)
    return search_payload, manifest



def fetch_subreplies(browser: BrowserClient, aid: str, root_rpid: str, subreply_limit: LimitValue) -> list[dict[str, Any]]:
    page = 1
    page_size = 20
    collected: list[dict[str, Any]] = []
    while True:
        url = f"https://api.bilibili.com/x/v2/reply/reply?type=1&oid={aid}&root={root_rpid}&ps={page_size}&pn={page}"
        payload = browser.fetch_json(url)
        replies = ((payload.get("data") or {}).get("replies") or [])
        if not replies:
            break
        for reply in replies:
            collected.append(simplify_reply(reply))
            if subreply_limit is not None and len(collected) >= subreply_limit:
                return collected[:subreply_limit]
        page_info = (payload.get("data") or {}).get("page") or {}
        count = page_info.get("count") or len(collected)
        size = page_info.get("size") or page_size
        if len(collected) >= count or len(replies) < size:
            break
        page += 1
    return collected if subreply_limit is None else collected[:subreply_limit]



def fetch_comments(browser: BrowserClient, aid: str, mode: int, limit: LimitValue, subreply_limit: LimitValue) -> list[dict[str, Any]]:
    nav = browser.fetch_json("https://api.bilibili.com/x/web-interface/nav")
    mixin_key = get_wbi_mixin_key(nav)
    next_cursor = 0
    next_offset: str | None = None
    collected: list[dict[str, Any]] = []
    seen_states = set()
    while True:
        state_key = (next_cursor, next_offset)
        if state_key in seen_states:
            break
        seen_states.add(state_key)
        params: dict[str, str | int] = {
            "mode": mode,
            "next": next_cursor,
            "oid": aid,
            "ps": 20,
            "type": 1,
            "wts": int(time.time()),
        }
        if next_offset:
            params["pagination_str"] = json.dumps({"offset": next_offset}, separators=(",", ":"))
        url = "https://api.bilibili.com/x/v2/reply/wbi/main?" + sign_wbi_params(params, mixin_key)
        payload = browser.fetch_json(url)
        data = payload.get("data") or {}
        replies = data.get("replies") or []
        if not replies:
            break
        for reply in replies:
            item = simplify_reply(reply)
            if item["reply_count"] and (subreply_limit is None or subreply_limit > 0):
                item["replies"] = fetch_subreplies(browser, aid, item["rpid"], subreply_limit)
            collected.append(item)
            if limit is not None and len(collected) >= limit:
                return collected[:limit]
        cursor = data.get("cursor") or {}
        if cursor.get("is_end"):
            break
        next_cursor = cursor.get("next", 0)
        next_offset = (cursor.get("pagination_reply") or {}).get("next_offset")
        if next_cursor == 0 and not next_offset:
            break
    return collected if limit is None else collected[:limit]



def resolve_video(browser: BrowserClient, bvid: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    browser.open(f"https://www.bilibili.com/video/{bvid}/")
    state = browser.get_video_state()
    aid = str(state.get("aid") or "")
    cid = str(state.get("cid") or "")
    actual_bvid = str(state.get("bvid") or bvid)
    if not aid or not cid or not actual_bvid:
        raise VideoStateMissingError()
    try:
        player_info = browser.fetch_json(f"https://api.bilibili.com/x/player/v2?cid={cid}&aid={aid}")
        if int(player_info.get("code", 0)) != 0:
            raise PlayerInfoFetchFailedError()
    except Exception as error:
        if isinstance(error, (BilibiliApiFailedError, PlayerInfoFetchFailedError)):
            raise PlayerInfoFetchFailedError() from error
        raise
    subtitles = ((player_info.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
    meta = VideoMeta(
        title=state.get("title") or "",
        aid=aid,
        bvid=actual_bvid,
        cid=cid,
        desc=state.get("desc") or "",
        owner_name=state.get("owner_name") or "",
        reply_count=state.get("reply_count") or 0,
        pubdate=timestamp_to_iso(state.get("pubdate") or 0),
        url=state.get("url") or f"https://www.bilibili.com/video/{bvid}/",
    )
    return to_plain_data(meta), subtitles



def build_meta_payload(meta: dict[str, Any], subtitle_tracks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "video": {
            "bvid": meta["bvid"],
            "aid": meta["aid"],
            "cid": meta["cid"],
            "title": meta["title"],
            "owner_name": meta["owner_name"],
            "pubdate": meta["pubdate"],
            "reply_count": meta["reply_count"],
            "url": meta["url"],
        },
        "availability": {
            "subtitles": {
                "track_count": len(subtitle_tracks),
                "langs": [track.get("lan") for track in subtitle_tracks],
            },
            "comments": {"reply_count": meta["reply_count"]},
        },
    }



def write_meta_artifact(output_dir: Path, meta: dict[str, Any]) -> list[str]:
    write_json(output_dir / "meta.json", meta)
    return ["meta.json"]



def reset_output_dir(output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir



def reset_output_subdir(output_dir: Path, name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    return target



def prune_output_root(output_dir: Path) -> None:
    managed_names = {"README.md", "meta.json", "comments", "subtitles"}
    if not output_dir.exists():
        return
    for path in output_dir.iterdir():
        if path.name in managed_names:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()



def list_artifact_files(output_dir: Path | None) -> list[str]:
    if output_dir is None or not output_dir.exists():
        return []
    return sorted(
        str(path.relative_to(output_dir))
        for path in output_dir.rglob("*")
        if path.is_file()
    )



def exported_subtitle_tracks(output_dir: Path, subtitle_tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    subtitles_dir = output_dir / "subtitles"
    if not subtitles_dir.exists():
        return []

    exported_langs: list[str] = []
    for path in sorted(subtitles_dir.iterdir()):
        if not path.is_file() or path.name == "tracks.json":
            continue
        for suffix in (".plain.txt", ".srt", ".txt", ".json"):
            if path.name.endswith(suffix):
                lang = path.name[:-len(suffix)]
                if lang and lang not in exported_langs:
                    exported_langs.append(lang)
                break

    return [track for track in subtitle_tracks if (track.get("lan") or "") in exported_langs]



def write_summary_artifact(
    meta: dict[str, Any],
    subtitle_tracks: list[dict[str, Any]],
    output_dir: Path,
    session_name: str,
    comment_limit: LimitValue = None,
    subreply_limit: LimitValue = None,
) -> list[str]:
    prune_output_root(output_dir)
    current_files = list_artifact_files(output_dir)
    if "README.md" not in current_files:
        current_files = [*current_files, "README.md"]
    summary = summary_markdown(
        meta,
        exported_subtitle_tracks(output_dir, subtitle_tracks),
        output_dir,
        current_files,
        session_name,
        comment_limit,
        subreply_limit,
    )
    write_text(output_dir / "README.md", summary)
    return list_artifact_files(output_dir)



def normalize_subtitle_lang(value: str) -> str:
    return value.strip().lower().replace("_", "-")



def find_subtitle_track(subtitle_tracks: list[dict[str, Any]], target_lang: str) -> dict[str, Any] | None:
    normalized_target = normalize_subtitle_lang(target_lang)
    for track in subtitle_tracks:
        if normalize_subtitle_lang(track.get("lan") or "") == normalized_target:
            return track
    return None



def find_subtitle_track_by_prefix(subtitle_tracks: list[dict[str, Any]], prefix: str) -> dict[str, Any] | None:
    for track in subtitle_tracks:
        if normalize_subtitle_lang(track.get("lan") or "").startswith(prefix):
            return track
    return None



def select_subtitle_track(subtitle_tracks: list[dict[str, Any]], requested_lang: str | None) -> dict[str, Any]:
    if not subtitle_tracks:
        raise SubtitleTracksUnavailableError()
    if requested_lang:
        track = find_subtitle_track(subtitle_tracks, requested_lang)
        if track is None:
            raise SubtitleLangNotFoundError([requested_lang])
        return track
    for exact_lang, prefix in (("ai-zh", "zh"), ("ai-en", "en"), ("ai-ja", "ja")):
        track = find_subtitle_track(subtitle_tracks, exact_lang)
        if track is not None:
            return track
        track = find_subtitle_track_by_prefix(subtitle_tracks, prefix)
        if track is not None:
            return track
    return subtitle_tracks[0]



def run_subtitles(
    browser: BrowserClient,
    meta: dict[str, Any],
    subtitle_tracks: list[dict[str, Any]],
    out_dir: Path | None,
    lang: str | None,
    session_name: str,
    comment_limit: LimitValue | None = None,
    subreply_limit: LimitValue | None = None,
    include_summary: bool = False,
) -> tuple[dict[str, Any], ArtifactManifest]:
    selected_track = select_subtitle_track(subtitle_tracks, lang)

    written_files: list[str] = []
    if out_dir is not None:
        subtitle_json = http_get_json(absolute_subtitle_url(selected_track["subtitle_url"]))
        subtitles_dir = reset_output_subdir(out_dir, "subtitles")
        write_json(subtitles_dir / "tracks.json", subtitle_tracks)
        written_files.append("subtitles/tracks.json")
        base_name = selected_track["lan"]
        write_json(subtitles_dir / f"{base_name}.json", subtitle_json)
        write_text(subtitles_dir / f"{base_name}.txt", render_subtitle_txt(subtitle_json))
        write_text(subtitles_dir / f"{base_name}.plain.txt", render_subtitle_plain(subtitle_json))
        write_text(subtitles_dir / f"{base_name}.srt", render_subtitle_srt(subtitle_json))
        written_files.extend([
            f"subtitles/{base_name}.json",
            f"subtitles/{base_name}.txt",
            f"subtitles/{base_name}.plain.txt",
            f"subtitles/{base_name}.srt",
        ])
        if include_summary:
            written_files = write_summary_artifact(meta, subtitle_tracks, out_dir, session_name, comment_limit, subreply_limit)

    payload = {
        "video": {"bvid": meta["bvid"], "aid": meta["aid"], "cid": meta["cid"]},
        "subtitles": {
            "requested_langs": [lang] if lang else [],
            "available_langs": [track.get("lan") for track in subtitle_tracks],
            "fetched_langs": [selected_track.get("lan")],
            "tracks": [to_plain_data(SubtitleTrackSummary(lan=selected_track.get("lan") or "", lan_doc=selected_track.get("lan_doc") or ""))],
        },
    }
    manifest = ArtifactManifest(output_dir=str(out_dir) if out_dir is not None else None, files=written_files)
    return payload, manifest



def run_comments(
    browser: BrowserClient,
    meta: dict[str, Any],
    out_dir: Path | None,
    modes: list[str],
    comment_limit: LimitValue,
    subreply_limit: LimitValue,
    subtitle_tracks: list[dict[str, Any]] | None = None,
    session_name: str | None = None,
) -> tuple[dict[str, Any], ArtifactManifest]:
    summaries: dict[str, Any] = {}
    written_files: list[str] = []
    if out_dir is not None:
        comments_dir = reset_output_subdir(out_dir, "comments")
    for mode_name in modes:
        if mode_name not in MODE_MAP:
            raise CommentModeInvalidError(mode_name)
        comments = fetch_comments(browser, str(meta["aid"]), MODE_MAP[mode_name], comment_limit, subreply_limit)
        if not comments:
            raise CommentsUnavailableError(mode_name)
        if out_dir is not None:
            write_json(comments_dir / f"{mode_name}.json", comments)
            write_text(comments_dir / f"{mode_name}.md", comments_to_markdown(f"{mode_name} comments", comments))
            written_files.extend([f"comments/{mode_name}.json", f"comments/{mode_name}.md"])
        requested_limit: int | str = "all" if comment_limit is None else comment_limit
        sub_limit: int | str = "all" if subreply_limit is None else subreply_limit
        summaries[mode_name] = {
            "requested_limit": requested_limit,
            "fetched_roots": len(comments),
            "subreply_limit": sub_limit,
            "truncated": False if comment_limit is None else len(comments) >= int(comment_limit),
        }
    if out_dir is not None and subtitle_tracks is not None and session_name is not None:
        written_files = write_summary_artifact(meta, subtitle_tracks, out_dir, session_name, comment_limit, subreply_limit)
    payload = {
        "video": {"bvid": meta["bvid"], "aid": meta["aid"]},
        "comments": {"modes": summaries},
    }
    manifest = ArtifactManifest(output_dir=str(out_dir) if out_dir is not None else None, files=written_files)
    return payload, manifest



def run_inspect(
    browser: BrowserClient,
    meta: dict[str, Any],
    subtitle_tracks: list[dict[str, Any]],
    out_dir: Path,
    lang: str | None,
    modes: list[str],
    comment_limit: LimitValue,
    subreply_limit: LimitValue,
    session_name: str,
) -> tuple[dict[str, Any], ArtifactManifest]:
    reset_output_dir(out_dir)
    write_meta_artifact(out_dir, meta)
    subtitle_payload, _ = run_subtitles(
        browser,
        meta,
        subtitle_tracks,
        out_dir,
        lang,
        session_name,
        comment_limit,
        subreply_limit,
        include_summary=False,
    )
    comment_payload, _ = run_comments(
        browser,
        meta,
        out_dir,
        modes,
        comment_limit,
        subreply_limit,
        subtitle_tracks,
        session_name,
    )
    files = list_artifact_files(out_dir)
    meta_payload = build_meta_payload(meta, subtitle_tracks)
    payload = {
        "video": meta_payload["video"],
        "availability": meta_payload["availability"],
        "subtitles": subtitle_payload["subtitles"],
        "comments": comment_payload["comments"],
    }
    manifest = ArtifactManifest(output_dir=str(out_dir), files=files)
    return payload, manifest
