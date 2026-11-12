from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUPERVISOR = ROOT / "deploy/qnap/tunnel/supervise.sh"


@pytest.fixture
def runtime(tmp_path: Path) -> dict[str, str]:
    binary = tmp_path / "tunnel-client"
    binary.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, signal, sys, time\n"
        "root = pathlib.Path(os.environ['TEST_RUNTIME'])\n"
        "if sys.argv[1] == 'run':\n"
        " (root / 'pid').write_text(str(os.getpid()))\n"
        " if os.environ.get('TEST_CHILD_EXIT'): sys.exit(0)\n"
        " if os.environ.get('TEST_CHILD_STUBBORN'): signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        " while True: time.sleep(0.01)\n"
        "counter = root / 'checks'\n"
        "n = int(counter.read_text()) if counter.exists() else 0\n"
        "counter.write_text(str(n + 1))\n"
        "if os.environ.get('TEST_HEALTH_HANG'):\n"
        " signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        " while True: time.sleep(0.01)\n"
        "states = os.environ.get('TEST_HEALTH', '1').split(',')\n"
        "sys.exit(int(states[min(n, len(states)-1)]))\n"
    )
    binary.chmod(0o755)
    sleeper = tmp_path / "sleep"
    sleeper.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys, time\n"
        "with (pathlib.Path(os.environ['TEST_RUNTIME']) / 'sleeps').open('a') as f:\n"
        " f.write(sys.argv[1] + '\\n')\n"
        "time.sleep(0.05)\n"
    )
    sleeper.chmod(0o755)
    return {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "TEST_RUNTIME": str(tmp_path)}


def run_supervisor(runtime: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", str(SUPERVISOR)], env=runtime,
                          capture_output=True, text=True, timeout=5)


def test_repeated_health_failures_exit_for_docker_restart(runtime: dict[str, str]) -> None:
    result = run_supervisor(runtime)
    root = Path(runtime["TEST_RUNTIME"])
    assert result.returncode == 1
    assert (root / "checks").read_text() == "3"
    assert (root / "sleeps").read_text().splitlines()[:3] == ["210", "30", "30"]
    pid = int((root / "pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_success_resets_consecutive_failures(runtime: dict[str, str]) -> None:
    runtime["TEST_HEALTH"] = "1,1,0,1,1,1"
    result = run_supervisor(runtime)
    assert result.returncode == 1
    assert (Path(runtime["TEST_RUNTIME"]) / "checks").read_text() == "6"


def test_child_exit_requests_restart(runtime: dict[str, str]) -> None:
    runtime["TEST_CHILD_EXIT"] = "1"
    assert run_supervisor(runtime).returncode == 1


def test_failed_health_forcibly_stops_stubborn_child(runtime: dict[str, str]) -> None:
    runtime["TEST_CHILD_STUBBORN"] = "1"
    result = run_supervisor(runtime)
    assert result.returncode == 1
    pid = int((Path(runtime["TEST_RUNTIME"]) / "pid").read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_hung_health_probe_is_forcibly_bounded(runtime: dict[str, str]) -> None:
    root = Path(runtime["TEST_RUNTIME"])
    # Accelerate the production bounds while exercising real TERM/KILL behavior.
    timeout = root / "timeout"
    timeout.write_text(
        '#!/bin/sh\n'
        '[ "$1" = -k ] && [ "$2" = 1 ] && [ "$3" = 5 ] || exit 99\n'
        'shift 3\n'
        'exec /usr/bin/timeout -k 0.05 0.1 "$@"\n'
    )
    timeout.chmod(0o755)
    runtime["TEST_HEALTH_HANG"] = "1"
    result = run_supervisor(runtime)
    assert result.returncode == 1
    assert (root / "checks").read_text() == "3"


def test_normal_stop_terminates_child(runtime: dict[str, str]) -> None:
    runtime["TEST_HEALTH"] = "0"
    process = subprocess.Popen(["sh", str(SUPERVISOR)], env=runtime,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    root = Path(runtime["TEST_RUNTIME"])
    try:
        deadline = time.monotonic() + 3
        while not (root / "checks").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (root / "checks").exists()
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=3) == 0
        with pytest.raises(ProcessLookupError):
            os.kill(int((root / "pid").read_text()), 0)
    finally:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def test_reboot_recovery_configuration() -> None:
    base = (ROOT / "deploy/qnap/tunnel/docker-compose.yml").read_text()
    overlay = (ROOT / "deploy/qnap/tunnel/docker-compose.mtls.yml").read_text()
    dockerfile = (ROOT / "deploy/qnap/tunnel/Dockerfile").read_text()
    assert "MCP_STARTUP_WAIT_TIMEOUT=3m" in base
    assert "MCP_STARTUP_WAIT_TIMEOUT: 30s" not in overlay
    assert "start_period: 210s" in base
    assert 'ENTRYPOINT ["/bin/sh", "/usr/local/bin/tunnel-supervise"]' in dockerfile
