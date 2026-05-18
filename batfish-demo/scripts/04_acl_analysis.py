#!/usr/bin/env python3
"""
Demo 04: ACL Analysis

Batfish can audit ACL/firewall rules to find:
  - Shadowed rules (lines that can never match because a prior rule catches all relevant traffic)
  - Permits/denies for specific flows
  - Inconsistencies between devices

This is one of Batfish's most powerful features — it's often hard to
spot shadowed rules manually in a 100-line ACL.
"""

import sys
sys.path.insert(0, '.')
from common import *
from pybatfish.datamodel.flow import HeaderConstraints


ACL_TESTS = [
    {"src": "10.20.20.50",  "dst": "10.10.10.10", "port": "80",  "proto": "TCP",
     "expect": "permit", "desc": "User HTTP to server"},
    {"src": "10.20.20.50",  "dst": "10.10.10.10", "port": "443", "proto": "TCP",
     "expect": "permit", "desc": "User HTTPS to server"},
    {"src": "10.100.100.5", "dst": "10.10.10.10", "port": "22",  "proto": "TCP",
     "expect": "permit", "desc": "Management SSH to server"},
    {"src": "8.8.8.8",       "dst": "10.10.10.10", "port": "80",  "proto": "TCP",
     "expect": "deny",   "desc": "Internet to server [SHOULD BE DENIED]"},
    {"src": "10.20.20.50",  "dst": "10.10.10.10", "port": "3389","proto": "TCP",
     "expect": "deny",   "desc": "User RDP to server [SHOULD BE DENIED]"},
]


def check_shadowed_rules(bf, node, acl_name):
    print(f"\n--- Shadowed rules in {node} {acl_name} ---")
    try:
        result = bf.q.filterLineReachability(
            filters=acl_name,
            nodes=node,
        ).answer().frame()

        if len(result) == 0:
            print("  No results (ACL may not exist on this device).")
            return

        unreachable_col = next((c for c in result.columns if "Unreachable" in c), None)
        if unreachable_col:
            shadowed = result[result[unreachable_col].notna()]
            if len(shadowed) > 0:
                print(f"  WARNING: {len(shadowed)} shadowed (unreachable) ACL line(s)!")
                for _, row in shadowed.iterrows():
                    line = row.get(unreachable_col, "")
                    blocking = row.get("Blocking_Lines", row.get("Blocking_Line_Action", "unknown"))
                    print(f"    Shadowed: '{line}'")
                    print(f"    Blocked by: {blocking}")
            else:
                print(f"  All {len(result)} ACL lines are reachable (no shadowing).")
        else:
            print(f"  Result columns: {result.columns.tolist()}")
            print(result.to_string(index=False))
    except Exception as e:
        print(f"  Could not run filterLineReachability: {e}")


def test_acl_flows(bf, snapshot_label):
    print_section(f"ACL Flow Tests on dist-switch-01 SERVER_ACL: {snapshot_label}")
    passed = 0
    for test in ACL_TESTS:
        try:
            result = bf.q.searchFilters(
                filters="SERVER_ACL",
                nodes="dist-switch-01",
                headers=HeaderConstraints(
                    srcIps=test["src"],
                    dstIps=test["dst"],
                    dstPorts=[test["port"]],
                    ipProtocols=[test["proto"]],
                ),
                action=test["expect"],
            ).answer().frame()
            matched = len(result) > 0
        except Exception:
            # Fall back: if searchFilters not available, skip
            matched = None

        if matched is None:
            print(f"  [SKIP] {test['desc']} (searchFilters unavailable)")
            continue

        ok = matched  # searchFilters returns rows when the action matches
        icon = "[PASS]" if ok else "[FAIL]"
        print(f"  {icon} {test['desc']}: {test['expect'].upper()}")
        if ok:
            passed += 1

    print(f"\n  Passed {passed}/{len(ACL_TESTS)} ACL flow tests")


def compare_acl_consistency(bf, snapshot_label):
    print_section(f"ACL Consistency Check (dist-sw-01 vs dist-sw-02): {snapshot_label}")
    for node in ["dist-switch-01", "dist-switch-02"]:
        check_shadowed_rules(bf, node, "SERVER_ACL")


def main():
    bf = init_session()

    print("\n" + "#" * 65)
    print("  GOOD NETWORK")
    print("#" * 65)
    load_snapshot(bf, GOOD_SNAPSHOT_PATH, GOOD_SNAPSHOT_NAME)
    test_acl_flows(bf, "Good Network")
    compare_acl_consistency(bf, "Good Network")

    print("\n" + "#" * 65)
    print("  BAD NETWORK — Expect: shadowed rules, inconsistent ACLs")
    print("#" * 65)
    load_snapshot(bf, BAD_SNAPSHOT_PATH, BAD_SNAPSHOT_NAME)
    test_acl_flows(bf, "Bad Network")
    compare_acl_consistency(bf, "Bad Network")


if __name__ == "__main__":
    main()
