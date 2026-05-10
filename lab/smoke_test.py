#!/usr/bin/env python3
"""
Smoke test for the mock Cisco lab devices.

Connects to each device with paramiko (same library network_cli uses),
sends 'show running-config', and prints the result.  Exits non-zero if
any device fails to respond correctly.

Usage:
    python3 lab/smoke_test.py
"""
import sys
import time
import paramiko

DEVICES = [
    {"name": "router1", "port": 2221},
    {"name": "router2", "port": 2222},
    {"name": "router3", "port": 2223},
]

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


def recv_until_prompt(shell, timeout=10):
    """Read from the shell until an IOS prompt (> or #) is seen or timeout."""
    buf = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if shell.recv_ready():
            chunk = shell.recv(8192).decode("utf-8", errors="replace")
            buf += chunk
            stripped = buf.rstrip()
            if stripped.endswith(">") or stripped.endswith("#"):
                break
        time.sleep(0.05)
    return buf


def smoke_test(name, port):
    sep = "─" * 60
    print(f"\n{sep}")
    print(f" Device : {name}   Port : {port}")
    print(sep)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(
            hostname="127.0.0.1",
            port=port,
            username="admin",
            password="cisco",
            allow_agent=False,
            look_for_keys=False,
            timeout=10,
            auth_timeout=10,
        )
    except Exception as exc:
        print(f"{FAIL} SSH connection failed: {exc}")
        return False

    try:
        shell = client.invoke_shell(width=200, height=50)

        # Read banner + initial prompt
        banner = recv_until_prompt(shell, timeout=8)
        print(f"[banner]\n{banner.strip()}\n")

        if not banner.strip():
            print(f"{FAIL} No data received from device – mock may not be running.")
            return False

        # Send show running-config and capture output
        shell.send("show running-config\n")
        config_out = recv_until_prompt(shell, timeout=15)

        print(f"[show running-config – first 600 chars]\n{config_out[:600]}")

        if "hostname" not in config_out and "version" not in config_out:
            print(f"\n{FAIL} {name}: response did not look like a Cisco config.")
            return False

        print(f"\n{PASS} {name}: device is up and returning a valid config.")
        return True

    except Exception as exc:
        print(f"{FAIL} Error during shell interaction: {exc}")
        return False
    finally:
        client.close()


def main():
    results = {}
    for dev in DEVICES:
        results[dev["name"]] = smoke_test(dev["name"], dev["port"])

    print(f"\n{'═' * 60}")
    print(" Summary")
    print('═' * 60)
    for name, passed in results.items():
        status = PASS if passed else FAIL
        print(f"  {status}  {name}")

    if all(results.values()):
        print("\nAll devices passed.\n")
        sys.exit(0)
    else:
        print("\nOne or more devices FAILED. Check the output above.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
