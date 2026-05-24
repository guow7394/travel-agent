import os
import subprocess
import sys


def test_package_imports_from_installed_environment_without_pytest_pythonpath():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-c", "import travel_agent_service; print(travel_agent_service.__version__)"],
        cwd="/tmp",
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "0.1.0" in result.stdout

