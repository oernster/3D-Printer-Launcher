import json
import os
from pathlib import Path

import paramiko
import time


def _load_password() -> str:
    """Load the SSH password from a local JSON file next to this script.

    Expected structure of ``credentials.json`` in this folder::

        {"password": "makerbase"}

    The file is intentionally kept out of version control so that credentials
    are never committed to Git.
    """

    # Allow overriding via environment variable so packaged builds can be used
    # without writing a credentials file to disk.
    env_pw = os.environ.get("QIDI_WEBCAMD_PASSWORD")
    if isinstance(env_pw, str) and env_pw.strip():
        return env_pw.strip()

    cfg_path = Path(__file__).with_name("credentials.json")
    try:
        raw = cfg_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        example_path = Path(__file__).with_name("credentials.example.json")
        raise RuntimeError(
            f"Missing credentials file: {cfg_path}. "
            "Create it (or copy the example) with e.g. {\"password\": \"makerbase\"}. "
            f"Example file: {example_path}. "
            "Alternatively, set environment variable QIDI_WEBCAMD_PASSWORD."
        ) from exc

    try:
        data = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"Failed to parse {cfg_path}: {exc}") from exc

    pw = data.get("password")
    if not isinstance(pw, str) or not pw:
        raise RuntimeError(
            f"Invalid password in {cfg_path}: expected non-empty 'password' field."
        )
    return pw


def ssh_command(ip, username, password, command):
    # Create a new SSH client
    client = paramiko.SSHClient()
    # Automatically add host keys from the system host keys
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Connect to the SSH server
        client.connect(ip, username=username, password=password)
        # Start an interactive shell session
        ssh_session = client.invoke_shell()
        
        # Wait for the prompt
        time.sleep(1)
        
        # Send the command
        ssh_session.send(command + "\n")
        time.sleep(1)  # Wait for the command to execute
        
        # Send the exit command
        ssh_session.send("exit\n")
        time.sleep(0.5)
        
        # Receive the output
        output = ssh_session.recv(5000).decode()
        print(output)
        
    finally:
        # Close the connection
        client.close()

# User settings
ip_address = "192.168.1.120"
username = "root"
password = _load_password()

# Commands to execute
commands = "sudo service webcamd restart"

# Run the SSH command function
ssh_command(ip_address, username, password, commands)
