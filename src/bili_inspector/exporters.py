from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")



def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



def render_subtitle_txt(subtitle: dict[str, Any]) -> str:
    body = subtitle.get("body") or []
    lines = [f'[{item.get("from", 0):07.2f}-{item.get("to", 0):07.2f}] {item.get("content", "")}' for item in body]
    return "\n".join(lines).rstrip() + ("\n" if lines else "")



def render_subtitle_plain(subtitle: dict[str, Any]) -> str:
    body = subtitle.get("body") or []
    return "\n".join(item.get("content", "") for item in body if item.get("content")) + "\n"



def format_seconds(value: float) -> str:
    total_ms = int(round(value * 1000))
    hours = total_ms // 3_600_000
    remainder = total_ms % 3_600_000
    minutes = remainder // 60_000
    remainder %= 60_000
    seconds = remainder // 1000
    milliseconds = remainder % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"



def render_subtitle_srt(subtitle: dict[str, Any]) -> str:
    chunks: list[str] = []
    for index, item in enumerate(subtitle.get("body") or [], start=1):
        chunks.append(str(index))
        chunks.append(f"{format_seconds(item.get('from', 0))} --> {format_seconds(item.get('to', 0))}")
        chunks.append(item.get("content", ""))
        chunks.append("")
    return "\n".join(chunks)



def comments_to_markdown(title: str, comments: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", ""]
    for index, comment in enumerate(comments, start=1):
        lines.append(f'## {index}. {comment["user"]}  👍 {comment["like"]}  💬 {comment["reply_count"]}')
        lines.append("")
        lines.append(comment["message"] or "(空)")
        lines.append("")
        for reply in comment.get("replies") or []:
            lines.append(f'- {reply["user"]} | 👍 {reply["like"]}: {reply["message"]}')
        if comment.get("replies"):
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"



def summary_markdown(
    meta: dict[str, Any],
    subtitle_tracks: list[dict[str, Any]],
    output_dir: Path,
    written_files: list[str],
    session_name: str,
    comment_limit: int | None,
    subreply_limit: int | None,
) -> str:
    def fmt_limit(value: int | None) -> str:
        return "all" if value is None else str(value)

    subtitle_files = [name for name in written_files if name.startswith("subtitles/")]
    comment_files = [name for name in written_files if name.startswith("comments/")]

    lines = [
        f'# {meta.get("title", "B 站视频导出")}',
        "",
        "## 基本信息",
        "",
        f'- `session_name`: `{session_name}`',
        f'- `comment_limit`: `{fmt_limit(comment_limit)}`',
        f'- `subreply_limit`: `{fmt_limit(subreply_limit)}`',
        f'- `bvid`: `{meta.get("bvid", "")}`',
        f'- `aid`: `{meta.get("aid", "")}`',
        f'- `cid`: `{meta.get("cid", "")}`',
        f'- `作者`: {meta.get("owner_name", "")}',
        f'- `发布时间`: {meta.get("pubdate", "")}',
        f'- `评论数`: {meta.get("reply_count", "")}',
        "",
        "## 简介",
        "",
        meta.get("desc", "").strip() or "(空)",
        "",
        "## 实际导出字幕轨",
        "",
    ]
    if subtitle_tracks:
        for track in subtitle_tracks:
            lines.append(f'- `{track.get("lan")}` / {track.get("lan_doc")}')
    else:
        lines.append("- 未导出字幕文件")

    lines.extend([
        "",
        "## 字幕文件说明",
        "",
        "- `*.plain.txt`：纯文本，最适合 AI 直接阅读、总结、抽取主题。",
        "- `*.txt`：带时间区间，适合按时间顺序分析内容。",
        "- `*.srt`：标准字幕格式，适合播放器或字幕工具。",
        "- `*.json`：原始结构化字幕，适合程序化处理。",
        "",
        "## 实际生成的字幕文件",
        "",
    ])
    if subtitle_files:
        for name in subtitle_files:
            lines.append(f'- `{name}`')
    else:
        lines.append("- 未生成字幕文件")

    lines.extend([
        "",
        "## 评论文件说明",
        "",
        "- `comments/hot.json` / `comments/latest.json`：结构化数据，适合 AI 程序化解析。",
        "- `comments/hot.md` / `comments/latest.md`：便于快速浏览的人类可读版。",
        "- `hot` = 最热评论，`latest` = 最新评论。",
        "",
        "## 实际生成的评论文件",
        "",
    ])
    if comment_files:
        for name in comment_files:
            lines.append(f'- `{name}`')
    else:
        lines.append("- 未生成评论文件")

    other_files = [name for name in written_files if name not in subtitle_files and name not in comment_files]
    lines.extend(["", "## 其他生成文件", ""])
    for name in other_files:
        lines.append(f'- `{name}`')
    lines.extend(["", f'输出目录：`{output_dir}`', ""])
    return "\n".join(lines)
