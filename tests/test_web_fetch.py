# SPDX-License-Identifier: Apache-2.0
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


def _load_tool_module():
    root = Path(__file__).resolve().parents[1]
    control_plane = root / "control-plane"
    sys.path.insert(0, str(control_plane))
    spec = importlib.util.spec_from_file_location("cp_tool_web_fetch_test", control_plane / "cp" / "tool.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _load_tool_module()


def test_web_fetch_rejects_local_and_non_http_urls():
    assert "locale" in tool._tool_web_fetch({"url": "http://127.0.0.1/admin"})
    assert "http/https" in tool._tool_web_fetch({"url": "file:///etc/passwd"})
    assert "locale" in tool._tool_web_fetch({"url": "http://box.local/"})


def test_web_fetch_does_not_follow_redirects():
    class Response:
        status = 302
        reason = "Found"
        def getheader(self, name, default=None):
            return "http://127.0.0.1/" if name == "Location" else default

    class Connection:
        def __init__(self, *args, **kwargs): pass
        def connect(self): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): pass

    with patch.object(tool.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]), \
         patch.object(tool.http.client, "HTTPConnection", Connection):
        result = tool._tool_web_fetch({"url": "http://public.example/start"})
    assert "non seguito" in result
    assert "127.0.0.1" in result


def test_web_fetch_extracts_html_text():
    class Response:
        status = 200
        reason = "OK"
        def getheader(self, name, default=None):
            return "text/html; charset=utf-8" if name == "Content-Type" else default
        def read(self, amount):
            body = b"<html><script>bad()</script><h1>Moltbook</h1><p>Join steps</p></html>"
            if getattr(self, "read_once", False): return b""
            self.read_once = True
            return body[:amount]

    class Connection:
        def __init__(self, *args, **kwargs): pass
        def connect(self): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): pass

    with patch.object(tool.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]), \
         patch.object(tool.http.client, "HTTPConnection", Connection):
        result = tool._tool_web_fetch({"url": "http://public.example/skill.md"})
    assert "Moltbook" in result and "Join steps" in result
    assert "bad()" not in result
