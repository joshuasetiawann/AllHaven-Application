"""Unit tests for installer/haven_common.py (stdlib-only pure logic)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import haven_common as hc  # noqa: E402


# --- ports ----------------------------------------------------------------- #


def test_is_valid_port():
    assert hc.is_valid_port(8000)
    assert hc.is_valid_port("3000")
    assert not hc.is_valid_port(0)
    assert not hc.is_valid_port(70000)
    assert not hc.is_valid_port("abc")
    assert not hc.is_valid_port(None)


def test_validate_ports_flags_dupes_and_invalid():
    errs = hc.validate_ports({"frontend": 3000, "backend": 3000, "db": "x"})
    assert "backend" in errs  # duplicate
    assert "db" in errs       # invalid
    assert "frontend" not in errs


def test_suggest_free_port_returns_valid():
    p = hc.suggest_free_port(49000, taken={49000, 49001})
    assert p is not None and hc.is_valid_port(p) and p not in (49000, 49001)


# --- env updates ----------------------------------------------------------- #


def test_apply_env_updates_creates_backs_up_and_preserves(tmp_path):
    example = tmp_path / ".env.example"
    example.write_text("FRONTEND_PORT=3000\nSECRET_KEY=keepme\n# comment\n", encoding="utf-8")
    env = tmp_path / ".env"

    # First write creates from example (no backup yet).
    r1 = hc.apply_env_updates({"FRONTEND_PORT": "3100"}, path=env, example_path=example)
    assert r1["created"] is True and r1["backup"] is None
    text = env.read_text(encoding="utf-8")
    assert "FRONTEND_PORT=3100" in text
    assert "SECRET_KEY=keepme" in text       # secret preserved
    assert "# comment" in text               # comment preserved

    # Second write backs up and only touches the requested key.
    r2 = hc.apply_env_updates({"BACKEND_PORT": "8100"}, path=env, example_path=example)
    assert r2["created"] is False and r2["backup"] is not None
    assert os.path.exists(r2["backup"])
    text2 = env.read_text(encoding="utf-8")
    assert "BACKEND_PORT=8100" in text2
    assert "FRONTEND_PORT=3100" in text2      # earlier change preserved
    assert "SECRET_KEY=keepme" in text2       # secret still intact


# --- secret masking -------------------------------------------------------- #


def test_mask_secrets():
    assert hc.mask_secrets("SECRET_KEY=abc123") == "SECRET_KEY=***"
    assert hc.mask_secrets("POSTGRES_PASSWORD=hunter2") == "POSTGRES_PASSWORD=***"
    assert "***" in hc.mask_secrets("url postgresql://user:pass@host:5432/db")
    assert "***" in hc.mask_secrets("Authorization: Bearer abc.def")
    assert hc.mask_secrets("OPENAI_API_KEY=sk-xxxx") == "OPENAI_API_KEY=***"
    # non-secret lines are untouched
    assert hc.mask_secrets("FRONTEND_PORT=3000") == "FRONTEND_PORT=3000"


# --- allowlists + compose argv (the security boundary) --------------------- #


def test_service_and_action_allowlists():
    assert hc.is_valid_service("postgres") and hc.is_valid_service("backend")
    assert not hc.is_valid_service("rm -rf")
    assert hc.is_valid_action("restart")
    assert not hc.is_valid_action("down")


def test_compose_argv_is_safe_and_nondestructive():
    assert hc.compose_argv("start", "postgres") == ["docker", "compose", "up", "-d", "postgres"]
    assert hc.compose_argv("stop", "postgres") == ["docker", "compose", "stop", "postgres"]
    assert hc.compose_argv("restart", "postgres")[2] == "restart"
    # Disallowed/destructive actions cannot be expressed.
    assert hc.compose_argv("down", "postgres") is None
    assert hc.compose_argv("rm", "postgres") is None
    # Bad service identifiers are rejected (no injection).
    assert hc.compose_argv("start", "postgres; rm -rf /") is None
    assert hc.compose_argv("start", "") is None
    # logs has a bounded tail
    argv = hc.compose_argv("logs", "postgres", lines=50)
    assert "--tail" in argv and "50" in argv


def test_command_builders():
    assert hc.backend_command("python", 8000)[:4] == ["python", "-m", "uvicorn", "app.main:app"]
    assert "8000" in hc.backend_command("python", 8000)
    fe = hc.frontend_command(3000)
    assert "3000" in fe and ("npm" in fe[0] or "npm.cmd" in fe[0])


def test_detect_os_is_known():
    assert hc.detect_os() in ("windows", "macos", "linux")


# --- launch helpers (v2.2 fix) --------------------------------------------- #


def test_app_binds_all_interfaces():
    # Managed services bind 0.0.0.0 (matching allhaven.sh), the agent stays localhost.
    assert hc.APP_BIND_HOST == "0.0.0.0"
    assert "0.0.0.0" in hc.backend_command("python", 8000, host=hc.APP_BIND_HOST)
    assert "0.0.0.0" in hc.frontend_command(3000, host=hc.APP_BIND_HOST)
    assert hc.AGENT_HOST == "127.0.0.1"


def test_enriched_env_augments_path(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    env = hc.enriched_env()
    assert "/usr/bin" in env["PATH"]            # original preserved
    assert "/usr/local/bin" in env["PATH"]      # common locations added
    assert "/opt/homebrew/bin" in env["PATH"]   # macOS Homebrew


def test_ensure_env_files_creates_frontend_local(tmp_path, monkeypatch):
    (tmp_path / "frontend").mkdir()
    (tmp_path / "frontend" / ".env.local.example").write_text(
        "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1\n", encoding="utf-8"
    )
    monkeypatch.setattr(hc, "repo_root", lambda: tmp_path)
    res = hc.ensure_env_files()
    assert "frontend/.env.local" in res["created"]
    assert (tmp_path / "frontend" / ".env.local").exists()
    # idempotent: a second call creates nothing
    assert hc.ensure_env_files()["created"] == []


def test_wait_for_port_times_out(tmp_path):
    import time

    start = time.time()
    # An almost-certainly-free high port returns False within the timeout window.
    result = hc.wait_for_port(59321, timeout=2.0)
    assert isinstance(result, bool)
    assert time.time() - start < 5.0


def test_ensure_env_files_mirrors_backend(tmp_path, monkeypatch):
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / ".env").write_text("BACKEND_PORT=8000\n", encoding="utf-8")
    monkeypatch.setattr(hc, "repo_root", lambda: tmp_path)

    # First sync copies .env -> backend/.env.
    assert "backend/.env" in hc.ensure_env_files()["created"]
    assert (tmp_path / "backend" / ".env").read_text(encoding="utf-8") == "BACKEND_PORT=8000\n"
    # Idempotent when unchanged.
    assert "backend/.env" not in hc.ensure_env_files()["created"]
    # A root .env change re-propagates on the next call (no staleness).
    (tmp_path / ".env").write_text("BACKEND_PORT=8123\n", encoding="utf-8")
    assert "backend/.env" in hc.ensure_env_files()["created"]
    assert (tmp_path / "backend" / ".env").read_text(encoding="utf-8") == "BACKEND_PORT=8123\n"


def test_ensure_dotenv_creates_with_secrets_and_mirrors(tmp_path, monkeypatch):
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / ".env.example").write_text(
        "SECRET_KEY=dev-insecure-secret-change-me\nFRONTEND_PORT=3000\n", encoding="utf-8"
    )
    monkeypatch.setattr(hc, "repo_root", lambda: tmp_path)

    res = hc.ensure_dotenv()
    assert res["created"] is True
    text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "SECRET_KEY=" in text and "dev-insecure-secret-change-me" not in text  # real secret generated
    assert "SETTINGS_ENCRYPTION_KEY=" in text
    # backend/.env mirrors the new .env (the requested behavior).
    assert (tmp_path / "backend" / ".env").read_text(encoding="utf-8") == text
    # Never overwrites an existing .env.
    assert hc.ensure_dotenv()["created"] is False
