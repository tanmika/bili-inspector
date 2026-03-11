from bili_inspector.errors import EXIT_CLI, InvalidBvidError, SubtitleLangNotFoundError
from bili_inspector.cli import error_envelope
from bili_inspector.models import CommandContext



def test_invalid_bvid_maps_to_exit_code_2():
    error = InvalidBvidError("foo")
    assert error.code == "E_INVALID_BVID"
    assert error.exit_code == EXIT_CLI



def test_error_envelope_shape():
    ctx = CommandContext(command="subtitles", bvid="BV1aurMBCEkE", keyword=None, page=None, limit=None, session_name="main", out_dir=None, json_output=True, verbose=False)
    envelope = error_envelope(ctx, SubtitleLangNotFoundError(["ai-en"]))
    data = envelope.to_dict()
    assert data["ok"] is False
    assert data["command"] == "subtitles"
    assert data["input"]["bvid"] == "BV1aurMBCEkE"
    assert data["error"]["code"] == "E_SUBTITLE_LANG_NOT_FOUND"
    assert data["error"]["stage"] == "subtitles.select_tracks"
