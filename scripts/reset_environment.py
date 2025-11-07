#!/usr/bin/env python3
"""
Reset local services and reseed sample data for end-to-end UI testing.

Steps performed:
1. docker-compose down --volumes --remove-orphans
2. docker-compose up -d (optionally with --build)
3. Wait for the API health endpoint to respond
4. Run DB migrations
5. Seed sample NDA documents
6. (optional) Load competency questions via the API
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from http.client import RemoteDisconnected


def find_compose_command() -> list[str]:
    """Return the base docker compose command to use."""
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    raise RuntimeError("Neither docker-compose nor docker compose is available on PATH.")


def run_command(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and stream output."""
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check)


def wait_for_api(url: str, timeout: int = 300, interval: int = 5) -> None:
    """Poll the API health endpoint until it responds or timeout elapses."""
    deadline = time.time() + timeout
    last_exc: Exception | None = None
    attempt = 1
    start = time.time()
    while time.time() < deadline:
        try:
            with urlopen(url) as response:
                if 200 <= response.status < 500:
                    print(f"API responded with status {response.status}; continuing.")
                    return
        except (URLError, RemoteDisconnected) as exc:
            last_exc = exc
            elapsed = int(time.time() - start)
            print(
                f"Waiting for API ({url}) – attempt {attempt}, elapsed {elapsed}s: {exc}"
            )
            attempt += 1
        time.sleep(interval)
    raise TimeoutError(
        f"API did not become ready within {timeout} seconds ({url}). Last error: {last_exc}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset local NDA stack and reseed data.")
    parser.add_argument(
        "--docs-dir",
        default="data",
        help="Directory containing sample NDA documents to ingest (default: data)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000/healthz",
        help="API health endpoint to poll while waiting for readiness.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip docker compose build (defaults to building images).",
    )
    parser.add_argument(
        "--load-competency",
        action="store_true",
        help="Load competency questions via scripts/load_competency_questions.py after seeding documents.",
    )
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="Run API pytest suite after seeding to verify the stack.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    compose = find_compose_command()

    # Ensure shared model cache exists so downloads persist between runs
    cache_dir = project_root / ".cache" / "huggingface"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: tear down existing services
    run_command(compose + ["down", "--volumes", "--remove-orphans"], cwd=project_root)

    # Step 2: rebuild images (unless skipped)
    if not args.no_build:
        run_command(compose + ["build", "--parallel"], cwd=project_root)

    # Step 3: bring services back up
    up_cmd = compose + ["up", "-d"]
    run_command(up_cmd, cwd=project_root)

    # Step 4: wait for API readiness
    print("\nWaiting for API to become ready...")
    wait_for_api(args.api_url)

    # Step 5: migrate database
    run_command(
        compose + ["exec", "api", "python", "-m", "api.db.migrations.001_init_schema"],
        cwd=project_root,
    )

    # Step 6: seed documents
    run_command(
        compose
        + [
            "exec",
            "api",
            "python",
            "scripts/seed_data.py",
            "--docs-dir",
            args.docs_dir,
        ],
        cwd=project_root,
    )

    # Step 7: optional competency questions
    if args.load_competency:
        qa_pairs_path = project_root / "eval" / "qa_pairs.json"
        if not qa_pairs_path.exists():
            print(f"⚠️  Skipping competency load; missing {qa_pairs_path}")
        else:
            run_command(
                compose
                + [
                    "exec",
                    "api",
                "python",
                "scripts/load_competency_questions.py",
                "--use-api",
            ],
            cwd=project_root,
        )

    # Step 8: optional test suite
    if args.run_tests:
        run_command(
            compose + ["exec", "api", "pytest"],
            cwd=project_root,
        )

    print("\nReset complete. UI should now show freshly ingested documents.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
