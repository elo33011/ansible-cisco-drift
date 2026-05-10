#!/usr/bin/env python3
"""
Mock Cisco IOS-XE SSH device for Ansible network_cli testing.

Simulates a Cisco IOS-XE router over SSH, responding to common CLI
commands so that ansible.netcommon.network_cli + cisco.ios can connect
and run playbooks without real hardware.

Environment variables:
  DEVICE_HOSTNAME  - router hostname shown in the prompt (default: Router)
  SSH_USER         - accepted SSH username (default: admin)
  SSH_PASSWORD     - accepted SSH password (default: cisco)
  ENABLE_PASSWORD  - enable/become password (default: cisco)
  CONFIG_FILE      - path to the running-config to serve (default: /configs/device.cfg)
  SSH_PORT         - TCP port to listen on (default: 22)
"""
import asyncssh
import asyncio
import os
import sys

HOSTNAME = os.environ.get("DEVICE_HOSTNAME", "Router")
SSH_USER = os.environ.get("SSH_USER", "admin")
SSH_PASSWORD = os.environ.get("SSH_PASSWORD", "cisco")
ENABLE_PASSWORD = os.environ.get("ENABLE_PASSWORD", "cisco")
CONFIG_FILE = os.environ.get("CONFIG_FILE", "/configs/device.cfg")
SSH_PORT = int(os.environ.get("SSH_PORT", "22"))


def load_running_config():
    try:
        with open(CONFIG_FILE) as fh:
            return fh.read()
    except FileNotFoundError:
        return f"! ERROR: config file not found: {CONFIG_FILE}\n!\nend\n"


class CiscoSession(asyncssh.SSHServerSession):
    """Simulates an interactive Cisco IOS-XE CLI session."""

    def __init__(self):
        self._chan = None
        self._buf = ""
        self._privileged = False
        self._awaiting_enable_pass = False

    # ------------------------------------------------------------------ #
    # asyncssh session lifecycle                                           #
    # ------------------------------------------------------------------ #

    def connection_made(self, chan):
        self._chan = chan

    def pty_requested(self, term_type, term_modes, term_width, term_height,
                      term_pixwidth, term_pixheight):
        return True

    def shell_requested(self):
        return True

    def session_started(self):
        # Send an IOS-style banner then the initial unprivileged prompt.
        banner = (
            "\r\n"
            "============================================\r\n"
            f" {HOSTNAME} - Authorized Access Only\r\n"
            "============================================\r\n"
            "\r\n"
        )
        self._chan.write(banner + self._prompt())

    def data_received(self, data, datatype):
        self._buf += data
        # Process every complete line (handles \r\n, \n, or bare \r).
        while True:
            for sep in ("\r\n", "\n", "\r"):
                idx = self._buf.find(sep)
                if idx != -1:
                    line = self._buf[:idx]
                    self._buf = self._buf[idx + len(sep):]
                    self._handle_line(line.strip())
                    break
            else:
                break

    def eof_received(self):
        self._chan.exit(0)

    # ------------------------------------------------------------------ #
    # Command dispatcher                                                   #
    # ------------------------------------------------------------------ #

    def _prompt(self):
        return f"{HOSTNAME}#" if self._privileged else f"{HOSTNAME}>"

    def _write(self, text):
        self._chan.write(text)

    def _handle_line(self, cmd):
        # Enable password entry mode: next line is the password.
        if self._awaiting_enable_pass:
            self._awaiting_enable_pass = False
            # Accept any password in lab mode so tests are not blocked by creds.
            self._privileged = True
            self._write(f"\r\n{HOSTNAME}#")
            return

        if not cmd:
            self._write(f"\r\n{self._prompt()}")
            return

        lower = cmd.lower()

        if lower == "enable":
            self._awaiting_enable_pass = True
            self._write("\r\nPassword: ")

        elif lower == "disable":
            self._privileged = False
            self._write(f"\r\n{HOSTNAME}>")

        elif lower.startswith("terminal ") or lower.startswith("term "):
            # terminal length 0 / terminal width 512 – acknowledge silently.
            self._write(f"\r\n{self._prompt()}")

        elif lower in (
            "show running-config",
            "show run",
            "sh run",
            "sh running-config",
            "show running-config all",
        ):
            config = load_running_config()
            self._write(f"\r\n{config}\r\n{self._prompt()}")

        elif lower in ("show version",):
            self._write(
                f"\r\nCisco IOS XE Software, Version 17.03.01a\r\n"
                f"Technical Support: http://www.cisco.com/techsupport\r\n"
                f"{self._prompt()}"
            )

        elif lower in ("exit", "quit", "logout"):
            self._write("\r\n")
            self._chan.exit(0)

        elif lower == "end":
            # 'end' in config mode returns to exec – stay privileged.
            self._write(f"\r\n{self._prompt()}")

        else:
            self._write(f"\r\n% Unknown command or computer error\r\n{self._prompt()}")


class CiscoServer(asyncssh.SSHServer):
    """Accepts all connections – this is a lab mock, not a production device."""

    def begin_auth(self, username):
        # Return False = SSH "none" auth; the server accepts the connection
        # immediately without a password challenge.  This sidesteps the
        # paramiko <-> asyncssh auth-method negotiation entirely.
        # The lab is testing drift detection logic, not SSH authentication.
        return False

    def session_requested(self):
        return CiscoSession()


async def run():
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
    )
    _ = server  # keep reference so GC does not close the server
    print(
        f"[*] Mock Cisco IOS-XE  hostname={HOSTNAME}  port={SSH_PORT}  config={CONFIG_FILE}",
        flush=True,
    )
    await asyncio.get_running_loop().create_future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        sys.exit(0)
