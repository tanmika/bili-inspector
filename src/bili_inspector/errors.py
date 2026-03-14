from __future__ import annotations

from dataclasses import dataclass


EXIT_OK = 0
EXIT_CLI = 2
EXIT_ENV = 3
EXIT_AUTH = 4
EXIT_NOT_FOUND = 5
EXIT_REMOTE = 6
EXIT_INTERNAL = 7


@dataclass
class InspectorError(Exception):
    code: str
    message: str
    stage: str
    retryable: bool
    hint: str | None = None
    exit_code: int = EXIT_INTERNAL

    def __str__(self) -> str:
        return self.message


class CliUsageError(InspectorError):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="E_INVALID_ARGUMENTS",
            message=message,
            stage="cli.parse_args",
            retryable=False,
            hint="Run `bili-inspector --help` for usage.",
            exit_code=EXIT_CLI,
        )


class InvalidBvidError(InspectorError):
    def __init__(self, raw: str) -> None:
        super().__init__(
            code="E_INVALID_BVID",
            message=f"Invalid BVID: {raw}",
            stage="input.parse_bvid",
            retryable=False,
            hint="Use a BVID like BV1xxxxxxxxx.",
            exit_code=EXIT_CLI,
        )


class DependencyMissingError(InspectorError):
    def __init__(self, dependency: str, *, stage: str = "doctor.dependencies", hint: str | None = None) -> None:
        super().__init__(
            code="E_DEPENDENCY_MISSING",
            message=f"Missing dependency: {dependency}",
            stage=stage,
            retryable=False,
            hint=hint or f"Install or expose `{dependency}` in PATH.",
            exit_code=EXIT_ENV,
        )


class BrowserOpenFailedError(InspectorError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            code="E_BROWSER_OPEN_FAILED",
            message="Failed to open page with agent-browser",
            stage="browser.open_page",
            retryable=True,
            hint="Check agent-browser availability and whether the session can open bilibili.com.",
            exit_code=EXIT_REMOTE,
        )
        self.detail = detail


class SessionInvalidError(InspectorError):
    def __init__(self, detail: str = "", *, stage: str = "doctor.session") -> None:
        super().__init__(
            code="E_SESSION_INVALID",
            message="Session is invalid or not logged in",
            stage=stage,
            retryable=False,
            hint="Open a logged-in session with `agent-browser --headed --session-name main open https://www.bilibili.com/`.",
            exit_code=EXIT_AUTH,
        )
        self.detail = detail


class VideoStateMissingError(InspectorError):
    def __init__(self) -> None:
        super().__init__(
            code="E_VIDEO_STATE_MISSING",
            message="Failed to read video state from page context",
            stage="resolve_video.read_video_state",
            retryable=True,
            hint="Ensure the BVID exists and the page is accessible in the current browser session.",
            exit_code=EXIT_REMOTE,
        )


class PlayerInfoFetchFailedError(InspectorError):
    def __init__(self) -> None:
        super().__init__(
            code="E_PLAYER_INFO_FETCH_FAILED",
            message="Failed to fetch player info",
            stage="resolve_video.fetch_player_info",
            retryable=True,
            hint="Retry later or verify bilibili player APIs are reachable from the browser session.",
            exit_code=EXIT_REMOTE,
        )


class SubtitleTracksUnavailableError(InspectorError):
    def __init__(self) -> None:
        super().__init__(
            code="E_SUBTITLE_TRACKS_UNAVAILABLE",
            message="Subtitle tracks are unavailable",
            stage="subtitles.fetch_tracks",
            retryable=False,
            hint="Run `bili-inspector meta <bvid> --json` to inspect subtitle availability first.",
            exit_code=EXIT_NOT_FOUND,
        )


class SubtitleLangNotFoundError(InspectorError):
    def __init__(self, langs: list[str]) -> None:
        super().__init__(
            code="E_SUBTITLE_LANG_NOT_FOUND",
            message="Requested subtitle languages were not found",
            stage="subtitles.select_tracks",
            retryable=False,
            hint="Run `bili-inspector meta <bvid> --json` to inspect available subtitle langs first.",
            exit_code=EXIT_NOT_FOUND,
        )
        self.langs = langs


class CommentModeInvalidError(InspectorError):
    def __init__(self, mode: str) -> None:
        super().__init__(
            code="E_COMMENT_MODE_INVALID",
            message=f"Invalid comment mode: {mode}",
            stage="comments.parse_mode",
            retryable=False,
            hint="Use one or more of: hot, latest.",
            exit_code=EXIT_CLI,
        )


class CommentsUnavailableError(InspectorError):
    def __init__(self, mode: str) -> None:
        super().__init__(
            code="E_COMMENTS_UNAVAILABLE",
            message=f"Comments are unavailable for mode: {mode}",
            stage="comments.fetch_comments",
            retryable=False,
            hint="Try another mode or verify the video has public comments.",
            exit_code=EXIT_NOT_FOUND,
        )


class BilibiliApiFailedError(InspectorError):
    def __init__(self, stage: str, detail: str = "") -> None:
        super().__init__(
            code="E_BILIBILI_API_FAILED",
            message="Bilibili API request failed",
            stage=stage,
            retryable=True,
            hint="Retry later or inspect browser session/network state.",
            exit_code=EXIT_REMOTE,
        )
        self.detail = detail


class InternalInspectorError(InspectorError):
    def __init__(self, message: str = "Unexpected internal error", *, stage: str = "internal") -> None:
        super().__init__(
            code="E_INTERNAL",
            message=message,
            stage=stage,
            retryable=False,
            hint="Inspect stderr logs or rerun with --verbose.",
            exit_code=EXIT_INTERNAL,
        )
