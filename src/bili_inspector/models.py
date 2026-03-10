from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1"


@dataclass
class CommandContext:
    command: str
    bvid: str | None
    session_name: str
    out_dir: Path | None
    json_output: bool
    verbose: bool


@dataclass
class ArtifactManifest:
    output_dir: str | None
    files: list[str] = field(default_factory=list)


@dataclass
class ErrorPayload:
    code: str
    message: str
    stage: str
    retryable: bool
    hint: str | None = None


@dataclass
class ResultEnvelope:
    ok: bool
    schema_version: str
    command: str
    input: dict[str, Any]
    data: dict[str, Any] | None = None
    artifacts: ArtifactManifest | None = None
    warnings: list[str] = field(default_factory=list)
    error: ErrorPayload | None = None

    def to_dict(self) -> dict[str, Any]:
        return to_plain_data(self)


@dataclass
class VideoMeta:
    bvid: str
    aid: str
    cid: str
    title: str
    owner_name: str
    pubdate: str
    reply_count: int
    url: str
    desc: str = ""


@dataclass
class SubtitleTrackSummary:
    lan: str
    lan_doc: str


@dataclass
class CommentModeSummary:
    requested_limit: int | str
    fetched_roots: int
    subreply_limit: int | str
    truncated: bool


@dataclass
class DoctorCheckResult:
    name: str
    ok: bool
    message: str = ""
    hint: str | None = None


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_plain_data(val) for key, val in asdict(value).items() if val is not None}
    if isinstance(value, dict):
        return {key: to_plain_data(val) for key, val in value.items() if val is not None}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    return value
