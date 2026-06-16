"""v4.1 version-visibility tests: /health reports the version, and the version
sources stay consistent (VERSION == backend == package manifests == nav constant)."""
import json
import re
from pathlib import Path

from app.core.version import get_app_version
from tests.conftest import API

_ROOT = Path(__file__).resolve().parents[2]
EXPECTED = "4.1.0"


def test_version_helper_reads_version_file():
    assert get_app_version() == EXPECTED


def test_health_reports_version_and_profile(client):
    resp = client.get(f"{API}/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["app_version"] == EXPECTED
    assert data["deployment_profile"] in ("private", "client_portal", "public_demo")


def test_all_version_sources_agree():
    assert (_ROOT / "VERSION").read_text().strip() == EXPECTED
    for pkg in (_ROOT / "package.json", _ROOT / "frontend" / "package.json"):
        assert json.loads(pkg.read_text())["version"] == EXPECTED, pkg
    pyproject = (_ROOT / "backend" / "pyproject.toml").read_text()
    assert f'version = "{EXPECTED}"' in pyproject
    nav = (_ROOT / "frontend" / "components" / "layout" / "nav.ts").read_text()
    m = re.search(r'APP_VERSION\s*=\s*"v([\d.]+)"', nav)
    assert m and m.group(1) == EXPECTED
