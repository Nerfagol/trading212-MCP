from __future__ import annotations

import subprocess
import sys
import tarfile
from pathlib import Path


def test_sdist_excludes_private_deployment_state_without_gitignore(tmp_path: Path) -> None:
    """Source archives must remain safe when rebuilt outside a Git checkout."""
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "pyproject.toml").write_text((root / "pyproject.toml").read_text())
    (tmp_path / "README.md").write_text("Synthetic package fixture")
    (tmp_path / "LICENSE").write_text("MIT")
    private = [
        ".env", ".env.local", "deploy/qnap/tunnel/.env",
        "deploy/qnap/secrets/mtls/ca.key", "deploy/qnap/tunnel/secrets/control_plane_api_key",
        "deploy/qnap/storage.conf", "deploy/qnap/mtls.enabled",
        ".mtls-upgrade-fixture/source.txt", ".snapshots-upgrade-fixture/source.txt",
        "data/snapshots/private.csv", "logs/mcp.jsonl",
    ]
    public = [".env.example", "deploy/qnap/tunnel/.env.example",
              "src/trading212_mcp/__init__.py"]
    for name in private + public:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic fixture")
    subprocess.run([sys.executable, "-m", "build", "--sdist", "--no-isolation"],
                   cwd=tmp_path, check=True, capture_output=True)
    with tarfile.open(next((tmp_path / "dist").glob("*.tar.gz"))) as archive:
        names = {name.partition("/")[2] for name in archive.getnames()}
    assert not set(private) & names
    assert set(public) <= names
