from __future__ import annotations

import shutil
import subprocess
import sys


def _uv_command() -> list[str]:
    uv_binary = shutil.which("uv")
    if uv_binary is not None:
        return [uv_binary]
    return [sys.executable, "-m", "uv"]


COMMANDS: list[list[str]] = [
    [*_uv_command(), "run", "--group", "dev", "ruff", "check", "."],
    [*_uv_command(), "run", "--group", "dev", "mypy", "src", "tests"],
    [*_uv_command(), "run", "--group", "dev", "pytest"],
]


def main() -> int:
    for command in COMMANDS:
        print(f"> {' '.join(command)}", flush=True)
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
