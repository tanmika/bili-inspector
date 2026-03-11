from pathlib import Path

import pytest

from bili_inspector.cli import build_parser, default_output_dir, default_search_output_dir, extract_error_context
from bili_inspector.errors import CliUsageError


REPO_ROOT = Path("/Users/tanmika/WebProject/bili-inspector").resolve()



def test_meta_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["meta", "BV1aurMBCEkE"])
    assert args.command == "meta"
    assert args.bvid == "BV1aurMBCEkE"
    assert args.session_name == "main"
    assert args.json_output is False



def test_lang_is_single_value_and_mode_is_repeatable():
    parser = build_parser()
    args = parser.parse_args([
        "inspect",
        "BV1aurMBCEkE",
        "--lang",
        "ai-zh",
        "--mode",
        "hot",
        "--mode",
        "latest",
    ])
    assert args.lang == "ai-zh"
    assert args.mode == ["hot", "latest"]



def test_search_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["search", "原神", "启动器"])
    assert args.command == "search"
    assert args.keyword == ["原神", "启动器"]
    assert args.page == 1
    assert args.limit == 10
    assert args.save_raw is False



def test_search_limit_is_capped():
    parser = build_parser()
    with pytest.raises(CliUsageError):
        parser.parse_args(["search", "原神", "--limit", "21"])



def test_out_dir_option_is_removed():
    parser = build_parser()
    with pytest.raises(CliUsageError):
        parser.parse_args(["meta", "BV1aurMBCEkE", "--out-dir", "/tmp/out"])



def test_default_output_dir_uses_repo_root():
    assert default_output_dir("BV1aurMBCEkE") == REPO_ROOT / "output" / "BV1aurMBCEkE"



def test_default_search_output_dir_uses_repo_root():
    assert default_search_output_dir("原神 启动器") == REPO_ROOT / "output" / "search" / "原神-启动器"



def test_extract_error_context_preserves_json_and_bvid():
    ctx = extract_error_context(["meta", "BV1bad", "--json", "--session-name", "work"])
    assert ctx.command == "meta"
    assert ctx.bvid == "BV1bad"
    assert ctx.keyword is None
    assert ctx.json_output is True
    assert ctx.session_name == "work"
    assert ctx.out_dir == REPO_ROOT / "output" / "BV1bad"



def test_extract_error_context_preserves_search_input():
    ctx = extract_error_context(["search", "原神", "启动器", "--page", "2", "--limit", "5", "--save-raw", "--json"])
    assert ctx.command == "search"
    assert ctx.bvid is None
    assert ctx.keyword == "原神 启动器"
    assert ctx.page == 2
    assert ctx.limit == 5
    assert ctx.json_output is True
    assert ctx.out_dir == REPO_ROOT / "output" / "search" / "原神-启动器"
