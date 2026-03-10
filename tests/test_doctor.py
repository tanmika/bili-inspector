from bili_inspector.browser import run_doctor



def test_doctor_returns_early_when_agent_browser_missing(monkeypatch):
    monkeypatch.setattr("bili_inspector.browser.shutil.which", lambda name: None if name == "agent-browser" else "/usr/bin/python3")
    checks = run_doctor("main")
    assert [item.name for item in checks] == ["python", "agent_browser"]
    assert checks[0].ok is True
    assert checks[1].ok is False



def test_doctor_success(monkeypatch):
    monkeypatch.setattr("bili_inspector.browser.shutil.which", lambda name: f"/usr/bin/{name}")

    class FakeDoctorBrowser:
        def __init__(self, session_name):
            self.session_name = session_name

        def open(self, url):
            return None

        def nav_fetch_check(self):
            return None

    monkeypatch.setattr("bili_inspector.browser.DoctorBrowserClient", FakeDoctorBrowser)
    checks = run_doctor("main")
    assert [item.name for item in checks] == ["python", "agent_browser", "browser_open", "bilibili_nav_fetch"]
    assert all(item.ok for item in checks)
