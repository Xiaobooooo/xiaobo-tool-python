"""utils 模块测试"""
import json
import sys
from unittest.mock import MagicMock

import pytest

from xiaobo_tool.utils import (
    _resolve_txt_path,
    read_txt_file_lines,
    write_txt_file,
    json_get,
    raise_response_error,
    parse_cloudflare_error,
)


# ── json_get ──────────────────────────────────────────────

class TestJsonGet:
    def test_dict_simple(self):
        assert json_get({"a": 1}, "a") == 1

    def test_dict_nested(self):
        assert json_get({"a": {"b": {"c": 3}}}, "a/b/c") == 3

    def test_list_index(self):
        assert json_get({"a": [10, 20, 30]}, "a/1") == 20

    def test_missing_key_returns_default(self):
        assert json_get({"a": 1}, "b") is None
        assert json_get({"a": 1}, "b", "fallback") == "fallback"

    def test_list_out_of_range(self):
        assert json_get([1, 2], "5") is None

    def test_negative_index_returns_default(self):
        assert json_get([1, 2, 3], "-1") is None

    def test_empty_path_returns_data(self):
        data = {"x": 1}
        assert json_get(data, "") is data

    def test_non_container_returns_default(self):
        assert json_get({"a": 42}, "a/b") is None


# ── parse_cloudflare_error ────────────────────────────────

class TestParseCloudflareError:
    def test_none_input(self):
        assert parse_cloudflare_error(None) is None

    def test_empty_string(self):
        assert parse_cloudflare_error("") is None

    def test_5xx_error(self):
        html = '''
        <span class="code-label">Error code 502</span>
        <h1 class="x"><span class="inline-block">Bad Gateway</span></h1>
        '''
        result = parse_cloudflare_error(html)
        assert "502" in result
        assert "Bad Gateway" in result

    def test_1xxx_error(self):
        html = '''
        <span data-translate="error">Error</span> <span>1020</span>
        <h2 class="text-gray-600">Access denied</h2>
        '''
        result = parse_cloudflare_error(html)
        assert "1020" in result
        assert "Access denied" in result

    def test_blocked_page(self):
        html = '<h1 data-translate="block_headline">Sorry, you have been blocked</h1>'
        result = parse_cloudflare_error(html)
        assert "blocked" in result.lower()

    def test_code_only(self):
        html = '<span class="code-label">Error code 503</span>'
        result = parse_cloudflare_error(html)
        assert "503" in result

    def test_no_match(self):
        assert parse_cloudflare_error("<html><body>OK</body></html>") is None


# ── raise_response_error ──────────────────────────────────

class TestRaiseResponseError:
    @staticmethod
    def _mock_response(status_code=400, content_type="application/json", json_data=None, text=""):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"Content-Type": content_type}
        resp.text = text
        if json_data is not None:
            resp.json.return_value = json_data
        else:
            resp.json.side_effect = json.JSONDecodeError("", "", 0)
        return resp

    def test_json_message_field(self):
        resp = self._mock_response(json_data={"message": "bad request"})
        with pytest.raises(Exception, match="bad request"):
            raise_response_error("Test", resp)

    def test_json_custom_msg_key(self):
        resp = self._mock_response(json_data={"data": {"info": "custom error"}})
        with pytest.raises(Exception, match="custom error"):
            raise_response_error("Test", resp, msg_key="data/info")

    def test_json_error_field(self):
        resp = self._mock_response(json_data={"error": "something wrong"})
        with pytest.raises(Exception, match="something wrong"):
            raise_response_error("Test", resp)

    def test_fallback_status_code(self):
        resp = self._mock_response(status_code=500, content_type="text/plain", text="Internal")
        with pytest.raises(Exception, match="500"):
            raise_response_error("Test", resp)

    def test_html_cloudflare(self):
        html = '<div class="cf-error-details"><span class="code-label">Error code 403</span></div>'
        resp = self._mock_response(status_code=403, content_type="text/html", text=html)
        with pytest.raises(Exception, match="403"):
            raise_response_error("Test", resp)

    def test_html_non_cloudflare(self):
        resp = self._mock_response(status_code=403, content_type="text/html", text="<html>Forbidden</html>")
        with pytest.raises(Exception, match="403"):
            raise_response_error("Test", resp)


# ── _resolve_txt_path / read / write ─────────────────────

class TestFileOperations:
    def test_resolve_auto_suffix(self, tmp_path, monkeypatch):
        """自动补全 .txt 后缀"""
        (tmp_path / "data.txt").write_text("hello\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [str(tmp_path / "script.py")])
        path = _resolve_txt_path("data")
        assert path.suffix == ".txt"

    def test_resolve_missing_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", [str(tmp_path / "script.py")])
        with pytest.raises(FileNotFoundError):
            _resolve_txt_path("nonexistent")

    def test_resolve_allow_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", [str(tmp_path / "script.py")])
        path = _resolve_txt_path("newfile", allow_missing=True)
        assert path == tmp_path / "newfile.txt"

    def test_read_txt_file_lines(self, tmp_path, monkeypatch):
        f = tmp_path / "items.txt"
        f.write_text("aaa\n\nbbb\n  \nccc\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [str(tmp_path / "script.py")])
        lines = read_txt_file_lines("items")
        assert lines == ["aaa", "bbb", "ccc"]

    def test_write_txt_file_append(self, tmp_path, monkeypatch):
        write_txt_file("out", "second")


    def test_write_txt_file_overwrite(self, tmp_path, monkeypatch):
        f = tmp_path / "out.txt"
        f.write_text("old\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [str(tmp_path / "script.py")])
        write_txt_file("out", "new", append=False)
        content = f.read_text(encoding="utf-8")
        assert "old" not in content
        assert "new" in content

    def test_write_txt_file_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", [str(tmp_path / "script.py")])
        write_txt_file("list_out", ["a", "b", "c"], append=False, separator=",")
        content = (tmp_path / "list_out.txt").read_text(encoding="utf-8")
        assert content.strip() == "a,b,c"

    def test_resolve_data_dir_fallback(self, tmp_path, monkeypatch):
        """脚本目录找不到时回退到 data 目录"""
        script_dir = tmp_path / "project" / "scripts"
        script_dir.mkdir(parents=True)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "accounts.txt").write_text("acc1\nacc2\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [str(script_dir / "run.py")])
        path = _resolve_txt_path("accounts")
        assert path == data_dir / "accounts.txt"
