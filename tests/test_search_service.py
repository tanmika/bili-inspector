import shutil

from bili_inspector.cli import default_search_output_dir
from bili_inspector.service import run_search, strip_search_title_html


class FakeBrowser:
    def __init__(self):
        self.opened = []
        self.fetched = []

    def open(self, url):
        self.opened.append(url)

    def fetch_json(self, url):
        self.fetched.append(url)
        return {
            "code": 0,
            "data": {
                "numResults": 1234,
                "numPages": 62,
                "result": [
                    {
                        "title": "<em class=\"keyword\">示例</em> 关键词",
                        "bvid": "BV1aaaaaa111",
                        "pubdate": 1709286600,
                        "play": "12.3万",
                    },
                    {
                        "title": "无效卡片",
                        "bvid": "",
                        "pubdate": 1709286600,
                        "play": "999",
                    },
                    {
                        "title": "第二条",
                        "bvid": "BV1bbbbbb222",
                        "pubdate": 1709373000,
                        "play": "3.4万",
                    },
                ],
            },
        }



def test_strip_search_title_html():
    assert strip_search_title_html("<em class=\"keyword\">示例</em>&amp;关键词") == "示例&关键词"



def test_run_search_returns_compact_results_without_artifacts():
    browser = FakeBrowser()
    payload, manifest = run_search(browser, "示例 关键词", 1, 10)

    assert manifest is None
    assert payload == {
        "search": {
            "keyword": "示例 关键词",
            "page": 1,
            "limit": 10,
            "total": 1234,
            "pages": 62,
            "returned": 2,
            "results": [
                {
                    "title": "示例 关键词",
                    "bvid": "BV1aaaaaa111",
                    "pubdate": "2024-03-01 17:50:00",
                    "play": "12.3万",
                },
                {
                    "title": "第二条",
                    "bvid": "BV1bbbbbb222",
                    "pubdate": "2024-03-02 17:50:00",
                    "play": "3.4万",
                },
            ],
        }
    }
    assert browser.opened
    assert browser.fetched



def test_run_search_save_raw_writes_artifact():
    browser = FakeBrowser()
    out_dir = default_search_output_dir("示例 关键词")
    shutil.rmtree(out_dir, ignore_errors=True)

    try:
        payload, manifest = run_search(browser, "示例 关键词", 1, 1, save_raw=True, out_dir=out_dir)
        assert payload["search"]["returned"] == 1
        assert manifest is not None
        assert manifest.output_dir == str(out_dir)
        assert manifest.files == ["raw.json"]
        assert (out_dir / "raw.json").exists()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
