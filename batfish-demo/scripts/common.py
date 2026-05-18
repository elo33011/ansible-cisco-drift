"""Shared utilities and constants for Batfish demo scripts."""

import os
import sys

try:
    from pybatfish.client.session import Session
    from pybatfish.datamodel import *
    from pybatfish.datamodel.flow import HeaderConstraints, PathConstraints
except ImportError:
    print("ERROR: pybatfish not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

import pandas as pd

# Batfish connection
BATFISH_HOST = os.environ.get("BATFISH_HOST", "localhost")
NETWORK_NAME = "batfish-demo"

# Snapshot paths (relative to scripts/ directory)
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.dirname(SCRIPTS_DIR)

GOOD_SNAPSHOT_PATH = os.path.join(DEMO_DIR, "snapshots", "good-network")
BAD_SNAPSHOT_PATH = os.path.join(DEMO_DIR, "snapshots", "bad-network")
GOOD_SNAPSHOT_NAME = "good-network"
BAD_SNAPSHOT_NAME = "bad-network"

# Display settings
pd.set_option("display.max_colwidth", 80)
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 100)


def init_session(host=BATFISH_HOST):
    """Connect to Batfish and set the network context."""
    print(f"Connecting to Batfish at {host}...")
    bf = Session(host=host)
    bf.set_network(NETWORK_NAME)
    print("Connected.")
    return bf


def load_snapshot(bf, path, name, overwrite=True):
    """Load a network snapshot into Batfish."""
    print(f"\nLoading snapshot '{name}' from {path} ...")
    bf.init_snapshot(path, name=name, overwrite=overwrite)
    bf.set_snapshot(name)
    print(f"Snapshot '{name}' loaded.")
    return bf


def print_section(title):
    width = 65
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def check_result(condition, pass_msg, fail_msg):
    icon = "[PASS]" if condition else "[FAIL]"
    msg = pass_msg if condition else fail_msg
    print(f"  {icon} {msg}")
    return condition
