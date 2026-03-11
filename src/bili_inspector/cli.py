from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .browser import BrowserClient, run_doctor
from .errors import EXIT_INTERNAL, CliUsageError, InspectorError, InternalInspectorError
from .models import ArtifactManifest, CommandContext, ErrorPayload, ResultEnvelope, SCHEMA_VERSION, to_plain_data
from .service import (
    MODE_MAP,
    build_meta_payload,
    parse_bvid,
    parse_limit,
    parse_search_limit,
    parse_search_page,
    resolve_video,
    run_comments,
    run_inspect,
    run_search,
    run_subtitles,
    write_meta_artifact,
    write_summary_artifact,
)


class CliArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message)


class Logger:
    def __init__(self, verbose: bool) -> None:
        self.verbose = verbose

    def log(self, stage: str, message: str) -> None:
        if self.verbose:
            print(f"[{stage}] {message}", file=sys.stderr)



def default_output_dir(bvid: str) -> Path:
    return (Path(__file__).resolve().parents[2] / "output" / bvid).resolve()



def default_search_output_dir(keyword: str) -> Path:
    slug = "-".join(keyword.strip().split()) or "search"
    slug = re.sub(r"[\\/]+", "-", slug)
    return (Path(__file__).resolve().parents[2] / "output" / "search" / slug).resolve()



def add_global_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session-name", default="main", help="agent-browser session name; default main")
    parser.add_argument("--json", action="store_true", dest="json_output", help="write machine-readable JSON to stdout")
    parser.add_argument("--verbose", action="store_true", help="write stage logs to stderr")



def build_parser() -> argparse.ArgumentParser:
    parser = CliArgumentParser(prog="bili-inspector", description="AI-first CLI for inspecting Bilibili videos.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="fetch meta, subtitles, and comments")
    inspect_parser.add_argument("bvid", type=parse_bvid)
    inspect_parser.add_argument("--lang", help="subtitle language to fetch; default auto-selects one track")
    inspect_parser.add_argument("--mode", action="append", default=[], help="comment mode to fetch; repeatable; default hot + latest")
    inspect_parser.add_argument("--comment-limit", type=parse_limit, default=20, help="root comment limit per mode; supports all")
    inspect_parser.add_argument("--subreply-limit", type=parse_limit, default=10, help="subreply limit per root comment; supports all")
    add_global_options(inspect_parser)

    meta_parser = subparsers.add_parser("meta", help="fetch video metadata and availability summary")
    meta_parser.add_argument("bvid", type=parse_bvid)
    add_global_options(meta_parser)

    subtitles_parser = subparsers.add_parser("subtitles", help="fetch subtitle tracks and files")
    subtitles_parser.add_argument("bvid", type=parse_bvid)
    subtitles_parser.add_argument("--lang", help="subtitle language to fetch; default auto-selects one track")
    add_global_options(subtitles_parser)

    comments_parser = subparsers.add_parser("comments", help="fetch comments and subreplies")
    comments_parser.add_argument("bvid", type=parse_bvid)
    comments_parser.add_argument("--mode", action="append", default=[], help="comment mode to fetch; repeatable; default hot + latest")
    comments_parser.add_argument("--comment-limit", type=parse_limit, default=20, help="root comment limit per mode; supports all")
    comments_parser.add_argument("--subreply-limit", type=parse_limit, default=10, help="subreply limit per root comment; supports all")
    add_global_options(comments_parser)

    search_parser = subparsers.add_parser("search", help="search bilibili videos by keyword")
    search_parser.add_argument("keyword", nargs="+", help="search keyword")
    search_parser.add_argument("--page", type=parse_search_page, default=1, help="search result page; default 1")
    search_parser.add_argument("--limit", type=parse_search_limit, default=10, help="max compact results to return; default 10, max 20")
    search_parser.add_argument("--save-raw", action="store_true", help="save the full raw search payload under output/search/<keyword>/")
    add_global_options(search_parser)

    doctor_parser = subparsers.add_parser("doctor", help="check local environment readiness")
    add_global_options(doctor_parser)

    return parser



def envelope_input(ctx: CommandContext) -> dict[str, Any]:
    payload: dict[str, Any] = {"session_name": ctx.session_name}
    if ctx.bvid is not None:
        payload["bvid"] = ctx.bvid
    if ctx.keyword is not None:
        payload["keyword"] = ctx.keyword
    if ctx.page is not None:
        payload["page"] = ctx.page
    if ctx.limit is not None:
        payload["limit"] = ctx.limit
    return payload



def success_envelope(ctx: CommandContext, data: dict[str, Any], artifacts: ArtifactManifest | None = None, warnings: list[str] | None = None) -> ResultEnvelope:
    return ResultEnvelope(
        ok=True,
        schema_version=SCHEMA_VERSION,
        command=ctx.command,
        input=envelope_input(ctx),
        data=data,
        artifacts=artifacts,
        warnings=warnings or [],
    )



def error_envelope(ctx: CommandContext, error: InspectorError) -> ResultEnvelope:
    return ResultEnvelope(
        ok=False,
        schema_version=SCHEMA_VERSION,
        command=ctx.command,
        input=envelope_input(ctx),
        error=ErrorPayload(
            code=error.code,
            message=error.message,
            stage=error.stage,
            retryable=error.retryable,
            hint=error.hint,
        ),
    )



def print_result(envelope: ResultEnvelope, json_output: bool) -> None:
    payload = envelope.to_dict()
    if json_output:
        print(json.dumps(payload, ensure_ascii=False))
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))



def resolve_ctx(args: argparse.Namespace) -> CommandContext:
    bvid = getattr(args, "bvid", None)
    keyword_tokens = getattr(args, "keyword", None)
    keyword = " ".join(keyword_tokens).strip() if keyword_tokens else None
    out_dir = default_output_dir(bvid) if bvid else None
    if getattr(args, "save_raw", False) and keyword:
        out_dir = default_search_output_dir(keyword)
    return CommandContext(
        command=args.command,
        bvid=bvid,
        keyword=keyword,
        page=getattr(args, "page", None),
        limit=getattr(args, "limit", None),
        session_name=args.session_name,
        out_dir=out_dir,
        json_output=args.json_output,
        verbose=args.verbose,
    )



def run_command(args: argparse.Namespace) -> ResultEnvelope:
    ctx = resolve_ctx(args)
    logger = Logger(ctx.verbose)

    if args.command == "doctor":
        logger.log("doctor", "running environment checks")
        checks = [to_plain_data(item) for item in run_doctor(ctx.session_name)]
        return success_envelope(ctx, {"checks": checks}, None)

    if args.command == "search":
        logger.log("search.open", f"keyword={ctx.keyword} page={ctx.page} limit={ctx.limit}")
        browser = BrowserClient(ctx.session_name)
        payload, manifest = run_search(
            browser,
            ctx.keyword or "",
            ctx.page or 1,
            ctx.limit or 10,
            save_raw=bool(getattr(args, "save_raw", False)),
            out_dir=ctx.out_dir,
        )
        logger.log("search.results", f"returned={payload['search']['returned']}")
        return success_envelope(ctx, payload, manifest)

    logger.log("resolve_video", f"resolving {ctx.bvid}")
    browser = BrowserClient(ctx.session_name)
    meta, subtitle_tracks = resolve_video(browser, ctx.bvid or "")

    if args.command == "meta":
        logger.log("write_artifacts", "writing meta artifact")
        files = []
        if ctx.out_dir is not None:
            ctx.out_dir.mkdir(parents=True, exist_ok=True)
            write_meta_artifact(ctx.out_dir, meta)
            files = write_summary_artifact(meta, subtitle_tracks, ctx.out_dir, ctx.session_name)
        manifest = ArtifactManifest(output_dir=str(ctx.out_dir) if ctx.out_dir is not None else None, files=files)
        return success_envelope(ctx, build_meta_payload(meta, subtitle_tracks), manifest)

    if args.command == "subtitles":
        logger.log("fetch_subtitles", "fetching subtitle tracks")
        payload, manifest = run_subtitles(browser, meta, subtitle_tracks, ctx.out_dir, args.lang, ctx.session_name, include_summary=True)
        return success_envelope(ctx, payload, manifest)

    if args.command == "comments":
        modes = args.mode or list(MODE_MAP.keys())
        logger.log("fetch_comments", f"fetching modes={modes}")
        payload, manifest = run_comments(browser, meta, ctx.out_dir, modes, args.comment_limit, args.subreply_limit, subtitle_tracks, ctx.session_name)
        return success_envelope(ctx, payload, manifest)

    if args.command == "inspect":
        modes = args.mode or list(MODE_MAP.keys())
        logger.log("write_artifacts", "writing full inspection artifacts")
        payload, manifest = run_inspect(
            browser,
            meta,
            subtitle_tracks,
            ctx.out_dir or default_output_dir(ctx.bvid or ""),
            args.lang,
            modes,
            args.comment_limit,
            args.subreply_limit,
            ctx.session_name,
        )
        return success_envelope(ctx, payload, manifest)

    raise InternalInspectorError(f"Unsupported command: {args.command}", stage="cli.dispatch")



def extract_error_context(argv: list[str]) -> CommandContext:
    command = "unknown"
    bvid = None
    keyword = None
    page = None
    limit = None
    save_raw = False
    session_name = "main"
    json_output = False
    verbose = False

    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"inspect", "meta", "subtitles", "comments", "doctor", "search"}:
            command = token
            if token == "search":
                keyword_parts: list[str] = []
                probe = index + 1
                while probe < len(argv) and not argv[probe].startswith("-"):
                    keyword_parts.append(argv[probe])
                    probe += 1
                keyword = " ".join(keyword_parts).strip() or None
            elif token != "doctor" and index + 1 < len(argv) and not argv[index + 1].startswith("-"):
                bvid = argv[index + 1]
            index += 1
            continue
        if token == "--session-name" and index + 1 < len(argv):
            session_name = argv[index + 1]
            index += 2
            continue
        if token == "--page" and index + 1 < len(argv):
            page = int(argv[index + 1])
            index += 2
            continue
        if token == "--limit" and index + 1 < len(argv):
            limit = int(argv[index + 1])
            index += 2
            continue
        if token == "--save-raw":
            save_raw = True
            index += 1
            continue
        if token == "--json":
            json_output = True
            index += 1
            continue
        if token == "--verbose":
            verbose = True
            index += 1
            continue
        index += 1

    out_dir = default_output_dir(bvid) if bvid else None
    if save_raw and keyword:
        out_dir = default_search_output_dir(keyword)
    return CommandContext(
        command=command,
        bvid=bvid,
        keyword=keyword,
        page=page,
        limit=limit,
        session_name=session_name,
        out_dir=out_dir,
        json_output=json_output,
        verbose=verbose,
    )



def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        envelope = run_command(args)
        print_result(envelope, args.json_output)
        return 0
    except InspectorError as error:
        raw_argv = list(sys.argv[1:] if argv is None else argv)
        ctx = extract_error_context(raw_argv)
        if ctx.verbose:
            print(f"[{error.stage}] {error}", file=sys.stderr)
        print_result(error_envelope(ctx, error), ctx.json_output)
        return error.exit_code
    except Exception as error:
        wrapped = InternalInspectorError(str(error), stage="internal.unhandled")
        raw_argv = list(sys.argv[1:] if argv is None else argv)
        ctx = extract_error_context(raw_argv)
        if ctx.verbose:
            print(f"[{wrapped.stage}] {wrapped}", file=sys.stderr)
        print_result(error_envelope(ctx, wrapped), ctx.json_output)
        return EXIT_INTERNAL



def entrypoint() -> None:
    raise SystemExit(main())
