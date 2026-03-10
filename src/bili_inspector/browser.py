from __future__ import annotations

import json
import shutil
import subprocess
import time
from typing import Any

from .errors import (
    BilibiliApiFailedError,
    BrowserOpenFailedError,
    DependencyMissingError,
    SessionInvalidError,
)
from .models import DoctorCheckResult


class BrowserClient:
    def __init__(self, session_name: str) -> None:
        self.session_name = session_name

    def _run(self, args: list[str]) -> str:
        cmd = ["agent-browser", "--session-name", self.session_name] + args
        last_error: subprocess.CalledProcessError | None = None
        for attempt in range(3):
            try:
                return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
            except FileNotFoundError as error:
                raise DependencyMissingError("agent-browser") from error
            except subprocess.CalledProcessError as error:
                last_error = error
                if attempt < 2:
                    time.sleep(1 + attempt)
        output = last_error.output.strip() if last_error and last_error.output else ""
        raise RuntimeError(output or f"agent-browser failed: {cmd}")

    def open(self, url: str) -> None:
        try:
            self._run(["close"])
        except Exception:
            pass
        last_error: Exception | None = None
        for _ in range(2):
            try:
                self._run(["open", url])
                self._run(["wait", "1500"])
                return
            except Exception as error:
                last_error = error
                try:
                    self._run(["close"])
                except Exception:
                    pass
                time.sleep(1)
        if isinstance(last_error, BrowserOpenFailedError):
            raise last_error
        raise BrowserOpenFailedError(str(last_error or ""))

    def eval_json(self, js: str) -> Any:
        try:
            output = self._run(["eval", js])
        except SessionInvalidError:
            raise
        except DependencyMissingError:
            raise
        except Exception as error:
            raise BilibiliApiFailedError("browser.eval_json", str(error)) from error
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise BilibiliApiFailedError("browser.eval_json", output[:300]) from error

    def fetch_json(self, url: str) -> Any:
        payload = self.eval_json(
            f'''(async () => {{
  const res = await fetch({json.dumps(url)}, {{credentials:'include'}});
  const text = await res.text();
  return {{status: res.status, text}};
}})()'''
        )
        status = payload.get("status")
        text = payload.get("text", "")
        if status == 401:
            raise SessionInvalidError(text[:300], stage="browser.fetch_json")
        if status != 200:
            raise BilibiliApiFailedError("browser.fetch_json", f"HTTP {status} {url}")
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise BilibiliApiFailedError("browser.fetch_json", text[:300]) from error

    def get_video_state(self) -> dict[str, Any]:
        return self.eval_json(
            '''(() => {
  const state = window.__INITIAL_STATE__ || {};
  const vd = state.videoData || {};
  return {
    title: vd.title || '',
    aid: String(vd.aid || ''),
    bvid: vd.bvid || '',
    cid: String(vd.cid || ((vd.pages || [])[0] || {}).cid || ''),
    desc: vd.desc || '',
    owner_name: (vd.owner || {}).name || '',
    reply_count: ((vd.stat || {}).reply) || 0,
    pubdate: vd.pubdate || 0,
    url: location.href
  };
})()'''
        )


class DoctorBrowserClient(BrowserClient):
    def nav_fetch_check(self) -> None:
        payload = self.fetch_json("https://api.bilibili.com/x/web-interface/nav")
        if int(payload.get("code", -1)) != 0:
            raise SessionInvalidError(str(payload)[:300], stage="doctor.session")



def run_doctor(session_name: str) -> list[DoctorCheckResult]:
    checks: list[DoctorCheckResult] = []

    python_ok = shutil.which("python3") is not None
    checks.append(DoctorCheckResult(name="python", ok=python_ok, hint=None if python_ok else "Install python3."))

    browser_ok = shutil.which("agent-browser") is not None
    checks.append(
        DoctorCheckResult(
            name="agent_browser",
            ok=browser_ok,
            hint=None if browser_ok else "Install agent-browser and ensure it is in PATH.",
        )
    )
    if not browser_ok:
        return checks

    browser = DoctorBrowserClient(session_name)
    try:
        browser.open("https://www.bilibili.com/")
        checks.append(DoctorCheckResult(name="browser_open", ok=True))
    except Exception as error:
        checks.append(
            DoctorCheckResult(
                name="browser_open",
                ok=False,
                message=str(error),
                hint="Verify `agent-browser --session-name main open https://www.bilibili.com/` works.",
            )
        )
        return checks

    try:
        browser.nav_fetch_check()
        checks.append(DoctorCheckResult(name="bilibili_nav_fetch", ok=True))
    except SessionInvalidError as error:
        checks.append(
            DoctorCheckResult(
                name="bilibili_nav_fetch",
                ok=False,
                message=str(error),
                hint=error.hint,
            )
        )
    except Exception as error:
        checks.append(
            DoctorCheckResult(
                name="bilibili_nav_fetch",
                ok=False,
                message=str(error),
                hint="Check Bilibili access from the current browser session.",
            )
        )
    return checks
