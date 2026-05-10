#!/usr/bin/env python3
"""
Mock Cisco IOS-XE SSH device for Ansible network_cli testing.

Uses asyncssh's process_factory API (recommended for interactive shells)
instead of the low-level SSHServerSession API.  Each SSH connection gets
an async coroutine that reads lines from stdin and writes IOS-style
responses to stdout, exactly as a real Cisco device would over SSH.

Environment variables:
  DEVICE_HOSTNAME  - router hostname shown in the prompt  (default: Router)
  SSH_USER         - accepted SSH username                (default: admin)
  SSH_PASSWORD     - accepted SSH password                (default: cisco)
  ENABLE_PASSWORD  - enable/become password               (default: cisco)
  CONFIG_FILE      - path to the running-config to serve  (default: /configs/device.cfg)
  SSH_PORT         - TCP port to listen on                (default: 22)
"""
import asyncssh
import asyncio
import os
import sys

HOSTNAME       = os.environ.get("DEVICE_HOSTNAME",  "Router")
SSH_USER       = os.environ.get("SSH_USER",         "admin")
SSH_PASSWORD   = os.environ.get("SSH_PASSWORD",     "cisco")
ENABLE_PASSWORD= os.environ.get("ENABLE_PASSWORD",  "cisco")
CONFIG_FILE    = os.environ.get("CONFIG_FILE",      "/configs/device.cfg")
SSH_PORT       = int(os.environ.get("SSH_PORT",     "22"))


def load_running_config() -> str:
    try:
        with open(CONFIG_FILE) as fh:
            return fh.read()
    except FileNotFoundError:
        return f"!\n! ERROR: config file not found: {CONFIG_FILE}\n!\nend\n"


async def handle_client(process: asyncssh.SSHServerProcess) -> None:
    """
    Simulate a Cisco IOS-XE interactive CLI session.
    Called once per SSH connection by asyncssh's process_factory.
    """
    privileged          = False
    awaiting_enable_pass = False

    def prompt() -> str:
        return f"{HOSTNAME}#" if privileged else f"{HOSTNAME}>"

    # ── send IOS-style banner and initial prompt ──────────────────────────
    process.stdout.write(
        "\r\n"
        "============================================\r\n"
        f" {HOSTNAME} - Authorized Access Only\r\n"
        "============================================\r\n"
        "\r\n"
        f"{prompt()}"
    )

    # ── main command loop ─────────────────────────────────────────────────
    try:
        async for raw_line in process.stdin:
            cmd = raw_line.rstrip("\r\n").strip()

            # ── enable password entry ─────────────────────────────────────
            if awaiting_enable_pass:
                awaiting_enable_pass = False
                privileged = True           # accept any password in lab mode
                process.stdout.write(f"\r\n{HOSTNAME}#")
                continue

            lower = cmd.lower()

            if not cmd:
                process.stdout.write(f"\r\n{prompt()}")

            elif lower == "enable":
                awaiting_enable_pass = True
                process.stdout.write("\r\nPassword: ")

            elif lower == "disable":
                privileged = False
                process.stdout.write(f"\r\n{HOSTNAME}>")

            elif lower.startswith("terminal ") or lower.startswith("term "):
                # terminal length 0 / terminal width 512 – acknowledge only
                process.stdout.write(f"\r\n{prompt()}")

            elif lower in (
                "show running-config",
                "show run",
                "sh run",
                "sh running-config",
                "show running-config all",
            ):
                config = load_running_config()
                process.stdout.write(f"\r\n{config}\r\n{prompt()}")

            elif lower == "show privilege":
                # cisco.ios terminal plugin runs this after 'enable' to confirm
                # the session is at privilege level 15.  Must match exactly.
                process.stdout.write(
                    f"\r\nCurrent privilege level is 15\r\n{prompt()}"
                )

            elif lower == "show version":
                process.stdout.write(
                    "\r\nCisco IOS XE Software, Version 17.03.01a\r\n"
                    "Technical Support: http://www.cisco.com/techsupport\r\n"
                    f"{prompt()}"
                )

            elif lower in ("exit", "quit", "logout"):
                process.stdout.write("\r\n")
                break

            elif lower == "end":
                # 'end' in any config sub-mode returns to privileged exec
                process.stdout.write(f"\r\n{prompt()}")

            else:
                process.stdout.write(
                    f"\r\n% Unknown command or computer error\r\n{prompt()}"
                )

    except (asyncssh.BreakReceived, asyncssh.TerminalSizeChanged,
            asyncssh.DisconnectError):
        pass

    process.exit(0)


class CiscoServer(asyncssh.SSHServer):
    """Accepts all connections – lab mock, not a production device."""

    def begin_auth(self, username: str) -> bool:
        # Return False = SSH 'none' auth: accept without a password challenge.
        # This avoids the paramiko <-> asyncssh auth-method negotiation that
        # was previously causing BadAuthenticationType errors.
        return False


async def run() -> None:
    key_path = "/tmp/ssh_host_key"
    try:
        host_key = asyncssh.read_private_key(key_path)
    except (FileNotFoundError, asyncssh.KeyImportError):
        host_key = asyncssh.generate_private_key("ssh-rsa", key_size=2048)
        host_key.write_private_key(key_path)

    server = await asyncssh.create_server(
        CiscoServer,
        host="",
        port=SSH_PORT,
        server_host_keys=[host_key],
        process_factory=handle_client,  # <-- process_factory, not SSHServerSession
        allow_pty=True,
    )
    _ = server  # keep reference so GC does not close the listening socket
    print(
        f"[*] Mock Cisco IOS-XE  hostname={HOSTNAME}"
        f"  port={SSH_PORT}  config={CONFIG_FILE}",
        flush=True,
    )
    await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)
