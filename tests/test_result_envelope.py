from bili_inspector.cli import success_envelope
from bili_inspector.models import ArtifactManifest, CommandContext



def test_success_result_envelope_shape():
    ctx = CommandContext(command="meta", bvid="BV1aurMBCEkE", keyword=None, page=None, limit=None, session_name="main", out_dir=None, json_output=True, verbose=False)
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
    ctx = CommandContext(command="inspect", bvid="BV1aurMBCEkE", keyword=None, page=None, limit=None, session_name="main", out_dir=None, json_output=True, verbose=False)
    envelope = success_envelope(
        ctx,
        data={"video": {"bvid": "BV1aurMBCEkE"}},
        artifacts=ArtifactManifest(output_dir="/tmp/out", files=["README.md", "meta.json"]),
    )
    payload = envelope.to_dict()
    assert payload["warnings"] == []



def test_success_result_envelope_includes_search_input_without_artifacts():
    ctx = CommandContext(command="search", bvid=None, keyword="原神", page=1, limit=10, session_name="main", out_dir=None, json_output=True, verbose=False)
    envelope = success_envelope(
        ctx,
        data={"search": {"keyword": "原神", "page": 1, "limit": 10, "returned": 1, "results": []}},
    )
    payload = envelope.to_dict()
    assert payload == {
        "ok": True,
        "schema_version": "1",
        "command": "search",
        "input": {"session_name": "main", "keyword": "原神", "page": 1, "limit": 10},
        "data": {"search": {"keyword": "原神", "page": 1, "limit": 10, "returned": 1, "results": []}},
        "warnings": [],
    }
