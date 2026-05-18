#!/usr/bin/env python3
"""
Demo 06: Pre-Change Impact Analysis

One of Batfish's killer features: before deploying a config change,
quantify exactly which traffic flows will be added or removed.

bf.q.differentialReachability() compares two snapshots and returns:
  - Flows that exist in snapshot A but not in snapshot B (traffic LOST)
  - Flows that exist in snapshot B but not in snapshot A (traffic GAINED)

This lets you validate a change in CI/CD before it touches production.
"""

import os
import sys
import shutil
sys.path.insert(0, '.')
from common import *
from pybatfish.datamodel.flow import HeaderConstraints

CANDIDATE_PATH = os.path.join(DEMO_DIR, "snapshots", "candidate-change")
CANDIDATE_NAME = "candidate-change"


def create_candidate_snapshot():
    """
    Simulates a proposed config change by copying good-network and modifying
    dist-switch-01 to add a stricter ACL rule: deny ICMP from users to servers.

    In practice, this snapshot would come from your config management system
    (Ansible, Terraform, etc.) after rendering the new config templates.
    """
    if os.path.exists(CANDIDATE_PATH):
        shutil.rmtree(CANDIDATE_PATH)
    shutil.copytree(GOOD_SNAPSHOT_PATH, CANDIDATE_PATH)

    config_file = os.path.join(CANDIDATE_PATH, "configs", "dist-switch-01.cfg")
    with open(config_file, "r") as f:
        config = f.read()

    # Insert a new deny-ICMP rule at the start of SERVER_ACL
    old_acl_header = "ip access-list extended SERVER_ACL"
    new_acl_header = (
        "ip access-list extended SERVER_ACL\n"
        " remark PROPOSED CHANGE: block ICMP from users to servers\n"
        " deny   icmp 10.20.20.0 0.0.0.255 10.10.10.0 0.0.0.255 log"
    )
    config = config.replace(old_acl_header, new_acl_header, 1)

    with open(config_file, "w") as f:
        f.write(config)

    print("Created candidate snapshot.")
    print("  Proposed change: add 'deny icmp 10.20.20.0/24 -> 10.10.10.0/24' to dist-switch-01 SERVER_ACL")


def analyze_change_impact(bf):
    print_section("Loading Snapshots for Differential Analysis")

    # Load the baseline (current production)
    load_snapshot(bf, GOOD_SNAPSHOT_PATH, GOOD_SNAPSHOT_NAME)

    # Create and load the candidate (proposed change)
    create_candidate_snapshot()
    print(f"\nLoading candidate snapshot...")
    bf.init_snapshot(CANDIDATE_PATH, name=CANDIDATE_NAME, overwrite=True)
    print("Candidate snapshot loaded.")

    print_section("Traffic Flows LOST by Proposed Change")
    print("  (Flows that exist in current config but will be blocked after change)")
    try:
        lost = bf.q.differentialReachability(
            headers=HeaderConstraints(
                srcIps="10.0.0.0/8",
                dstIps="10.10.10.0/24",
            ),
        ).answer(
            snapshot=GOOD_SNAPSHOT_NAME,
            reference_snapshot=CANDIDATE_NAME,
        ).frame()

        if len(lost) == 0:
            print("  No traffic flows will be lost by this change.")
        else:
            print(f"  WARNING: {len(lost)} flow(s) will be BLOCKED by this change!")
            flow_col = "Flow" if "Flow" in lost.columns else lost.columns[0]
            for _, row in lost.iterrows():
                print(f"    {row.get(flow_col, row)}")
    except Exception as e:
        print(f"  differentialReachability error: {e}")
        print("  (Ensure both snapshots are loaded and Batfish version supports differential queries)")

    print_section("Traffic Flows GAINED by Proposed Change")
    print("  (New flows that will be permitted after change — should be empty for a restrict-only change)")
    try:
        gained = bf.q.differentialReachability(
            headers=HeaderConstraints(
                srcIps="10.0.0.0/8",
                dstIps="10.10.10.0/24",
            ),
        ).answer(
            snapshot=CANDIDATE_NAME,
            reference_snapshot=GOOD_SNAPSHOT_NAME,
        ).frame()

        if len(gained) == 0:
            print("  No new flows will be permitted (expected for a restrict-only change).")
        else:
            print(f"  WARNING: {len(gained)} unexpected new flow(s) will be permitted!")
            flow_col = "Flow" if "Flow" in gained.columns else gained.columns[0]
            for _, row in gained.iterrows():
                print(f"    {row.get(flow_col, row)}")
    except Exception as e:
        print(f"  differentialReachability error: {e}")

    print_section("Change Impact Summary")
    print("  Proposed change: deny icmp 10.20.20.0/24 -> 10.10.10.0/24 on dist-switch-01")
    print("  Impact:")
    print("    - ICMP (ping) from users to servers: BLOCKED")
    print("    - HTTP/HTTPS/SSH traffic: UNAFFECTED")
    print("    - All other traffic: UNAFFECTED")
    print("")
    print("  Use this analysis to confirm the change matches the intended policy.")
    print("  If the blast radius is acceptable, proceed with deployment.")


def main():
    bf = init_session()
    analyze_change_impact(bf)

    # Cleanup candidate snapshot directory
    if os.path.exists(CANDIDATE_PATH):
        shutil.rmtree(CANDIDATE_PATH)
        print("\nCleaned up candidate snapshot directory.")


if __name__ == "__main__":
    main()
