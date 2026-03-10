from bili_inspector.cli import success_envelope
from bili_inspector.models import ArtifactManifest, CommandContext



def test_success_result_envelope_shape():
    ctx = CommandContext(command="meta", bvid="BV1aurMBCEkE", session_name="main", out_dir=None, json_output=True, verbose=False)
    envelope = success_envelope(
        ctx,
        data={"video": {"bvid": "BV1aurMBCEkE"}},
        artifacts=ArtifactManifest(output_dir="/tmp/out", files=["README.md", "meta.json"]),
    )
    payload = envelope.to_dict()
    assert payload == {
        "ok": True,
        "schema_version": "1",
        "command": "meta",
        "input": {"session_name": "main", "bvid": "BV1aurMBCEkE"},
        "data": {"video": {"bvid": "BV1aurMBCEkE"}},
        "artifacts": {"output_dir": "/tmp/out", "files": ["README.md", "meta.json"]},
        "warnings": [],
    }



def test_success_result_envelope_allows_empty_warnings_for_inspect():
    ctx = CommandContext(command="inspect", bvid="BV1aurMBCEkE", session_name="main", out_dir=None, json_output=True, verbose=False)
    envelope = success_envelope(
        ctx,
        data={"video": {"bvid": "BV1aurMBCEkE"}},
        artifacts=ArtifactManifest(output_dir="/tmp/out", files=["README.md", "meta.json"]),
    )
    payload = envelope.to_dict()
    assert payload["warnings"] == []
