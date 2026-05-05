"""Automated deployment script for EVE Market Tool to Tencent Cloud.

Uses paramiko for SSH + SFTP. All paths normalized to Linux/POSIX format.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path, PurePosixPath

import paramiko

# ---- Config ----
SERVER_IP = "47.243.104.165"
SSH_USER = "root"
SSH_PASSWORD = "LSxqj1002>"
REMOTE_DIR = "/opt/eve-market-tool"
PROJECT_DIR = Path("F:/github/EVE_Market_Tool")

# Files/dirs to exclude from upload
EXCLUDE = {
    ".venv", ".git", "__pycache__", ".pytest_cache",
    "eve_market_tool.egg-info", "deploy_auto.py", "uv.lock",
    ".env.example", ".claude", "deploy.sh",
}


def ssh_connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SERVER_IP, username=SSH_USER, password=SSH_PASSWORD, timeout=15)
    return client


def run_ssh(client: paramiko.SSHClient, cmd: str, desc: str = "") -> tuple[str, str, int]:
    if desc:
        print(f"  {desc}...")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code


def _posix_path(*parts) -> str:
    """Build a POSIX path from parts (all forward slashes)."""
    return PurePosixPath(*parts).as_posix()


def step_install_docker(client: paramiko.SSHClient):
    print("\n[Step 1] Installing Docker...")
    out, _, code = run_ssh(client, "docker --version 2>&1")
    if code == 0:
        print(f"  Docker: {out.strip()}")
    else:
        run_ssh(client, "curl -fsSL https://get.docker.com | bash", "Installing Docker")
        run_ssh(client, "systemctl enable docker && systemctl start docker", "Starting Docker")

    out, _, code = run_ssh(client, "docker compose version 2>&1")
    if code == 0:
        print(f"  Compose: {out.strip()}")
    else:
        run_ssh(client, "apt-get update -qq && apt-get install -y -qq docker-compose-plugin")
    print("  [OK] Docker ready")


def step_upload_files(client: paramiko.SSHClient):
    print("\n[Step 2] Uploading project files...")
    sftp = client.open_sftp()

    def mkdir_p(remote_dir: str):
        parts = remote_dir.strip("/").split("/")
        cur = ""
        for p in parts:
            cur += "/" + p
            try:
                sftp.stat(cur)
            except FileNotFoundError:
                sftp.mkdir(cur)

    mkdir_p(REMOTE_DIR)
    uploaded = 0

    for root, dirs, files in os.walk(str(PROJECT_DIR)):
        # Convert Windows root to POSIX relative path
        root_path = Path(root)
        if root_path == PROJECT_DIR:
            rel_root = ""
        else:
            rel_root = root_path.relative_to(PROJECT_DIR).as_posix()

        # Filter excluded dirs in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDE and not (d.startswith(".") and d != ".env")]

        # Create remote directory
        if rel_root:
            mkdir_p(_posix_path(REMOTE_DIR, rel_root))

        for fname in files:
            if fname in EXCLUDE:
                continue
            if fname.startswith(".") and fname != ".env":
                continue

            local = (root_path / fname).as_posix()
            remote = _posix_path(REMOTE_DIR, rel_root, fname) if rel_root else _posix_path(REMOTE_DIR, fname)

            try:
                sftp.put(local, remote)
                uploaded += 1
                if uploaded % 20 == 0:
                    print(f"  Uploaded {uploaded} files...")
            except Exception as e:
                print(f"  [WARN] {fname}: {e}")

    sftp.close()
    print(f"  [OK] Uploaded {uploaded} files")


def step_build_and_start(client: paramiko.SSHClient):
    print("\n[Step 3] Building and starting containers...")

    # Verify file structure on server (debug)
    out, _, _ = run_ssh(client,
        f"ls {REMOTE_DIR}/app/api/v1/endpoints/ 2>&1",
        "Verifying uploaded files")
    print(f"  Files in endpoints: {out.strip()}")

    # Build
    out, err, code = run_ssh(client,
        f"cd {REMOTE_DIR} && docker compose build --pull 2>&1",
        "Building Docker images (may take 3-5 min)")

    if code != 0:
        # Show last 30 lines of output on failure
        lines = (out + err).split("\n")
        print("  [BUILD LOG] " + "\n  [BUILD LOG] ".join(lines[-30:]))
        print(f"\n  [ERROR] Build failed with exit code {code}")
        return False

    print("  [OK] Images built")

    # Start
    run_ssh(client,
        f"cd {REMOTE_DIR} && docker compose up -d 2>&1",
        "Starting containers")

    time.sleep(8)

    out, _, _ = run_ssh(client, f"cd {REMOTE_DIR} && docker compose ps 2>&1")
    print(f"  Containers:\n{out}")
    return True


def step_run_migrations(client: paramiko.SSHClient):
    print("\n[Step 4] Running database migrations...")
    out, err, code = run_ssh(client,
        f"cd {REMOTE_DIR} && docker compose exec -T app alembic upgrade head 2>&1")

    if code == 0:
        print(f"  [OK] {out.strip()}")
    else:
        print(f"  Migration output: {out}\n{err}")
        # Check if app is running anyway
        out2, _, _ = run_ssh(client, "curl -s http://localhost:8000/ 2>&1")
        if "EVE Market Tool" in out2:
            print("  [OK] App responding despite migration warning")


def step_open_firewall(client: paramiko.SSHClient):
    print("\n[Step 5] Configuring firewall...")
    run_ssh(client, "ufw allow 8000/tcp 2>&1")
    print("  [OK] ufw port 8000 opened")
    print("\n  *** IMPORTANT: Also open TCP port 8000 in Tencent Cloud console! ***")
    print("  *** https://console.cloud.tencent.com/lighthouse/firewall ***")


def final_verify(client: paramiko.SSHClient):
    print("\n[Step 6] Verifying deployment...")
    time.sleep(3)

    out, _, _ = run_ssh(client, "curl -s http://localhost:8000/ 2>&1", "Health check")
    print(f"  App response: {out.strip()[:200]}")

    out2, _, _ = run_ssh(client,
        "curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/docs 2>&1",
        "API docs check")
    print(f"  API docs: HTTP {out2.strip()}")


def main():
    print("=" * 60)
    print(f"EVE Market Tool — Deploying to {SERVER_IP}")
    print("=" * 60)

    client = ssh_connect()
    try:
        step_install_docker(client)
        step_upload_files(client)
        ok = step_build_and_start(client)
        if not ok:
            print("\n[FAILED] Build step failed. Check Docker build logs above.")
            sys.exit(1)
        step_run_migrations(client)
        step_open_firewall(client)
        final_verify(client)

        print("\n" + "=" * 60)
        print("DEPLOYMENT COMPLETE!")
        print("=" * 60)
        print(f"  App:       http://{SERVER_IP}:8000/")
        print(f"  API Docs:  http://{SERVER_IP}:8000/docs")
        print("=" * 60)
    finally:
        client.close()


if __name__ == "__main__":
    main()
