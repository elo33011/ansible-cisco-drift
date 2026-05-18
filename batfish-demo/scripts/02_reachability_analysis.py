#!/usr/bin/env python3
"""
Demo 02: Reachability Analysis

Tests whether specific traffic flows can traverse the network.
Batfish simulates packet forwarding through every device and reports
whether flows are ACCEPTED, DENIED, NULL_ROUTED, or NO_ROUTE.

Compares good-network vs bad-network to show which tests fail.
"""

import sys
sys.path.insert(0, '.')
from common import *
from pybatfish.datamodel.flow import HeaderConstraints


REACHABILITY_TESTS = [
    {
        "name": "Users -> Servers (HTTP)",
        "src": "10.20.20.0/24",
        "dst": "10.10.10.0/24",
        "proto": "TCP",
        "port": "80",
        "expect": "ACCEPTED",
    },
    {
        "name": "Users -> Servers (HTTPS)",
        "src": "10.20.20.0/24",
        "dst": "10.10.10.0/24",
        "proto": "TCP",
        "port": "443",
        "expect": "ACCEPTED",
    },
    {
        "name": "Management -> Servers (SSH)",
        "src": "10.100.100.0/24",
        "dst": "10.10.10.0/24",
        "proto": "TCP",
        "port": "22",
        "expect": "ACCEPTED",
    },
    {
        "name": "Users -> Servers (SSH) [SHOULD BE BLOCKED]",
        "src": "10.20.20.0/24",
        "dst": "10.10.10.0/24",
        "proto": "TCP",
        "port": "22",
        "expect": "DENIED",
    },
    {
        "name": "Internet -> Servers (HTTP) [SHOULD BE BLOCKED]",
        "src": "8.8.8.8/32",
        "dst": "10.10.10.50",
        "proto": "TCP",
        "port": "80",
        "expect": "DENIED",
    },
    {
        "name": "Users -> Management (SSH) [SHOULD BE BLOCKED]",
        "src": "10.20.20.0/24",
        "dst": "10.100.100.0/24",
        "proto": "TCP",
        "port": "22",
        "expect": "DENIED",
    },
]


def run_reachability_tests(bf, snapshot_label):
    print_section(f"Reachability Tests: {snapshot_label}")
    passed = 0
    failed = 0

    for test in REACHABILITY_TESTS:
        result = bf.q.reachability(
            headers=HeaderConstraints(
                srcIps=test["src"],
                dstIps=test["dst"],
                ipProtocols=[test["proto"]],
                dstPorts=[test["port"]],
            ),
            actions=["ACCEPTED", "DENIED", "NO_ROUTE", "NULL_ROUTED"],
        ).answer().frame()

        accepted = result[result["Action"] == "ACCEPTED"]
        blocked = result[result["Action"].isin(["DENIED", "NO_ROUTE", "NULL_ROUTED"])]

        if test["expect"] == "ACCEPTED":
            ok = len(accepted) > 0 and len(blocked) == 0
        else:
            ok = len(blocked) > 0 and len(accepted) == 0

        status = "PASS" if ok else "FAIL"
        icon = "[PASS]" if ok else "[FAIL]"
        if ok:
            passed += 1
        else:
            failed += 1

        if not ok and len(result) > 0:
            actual_actions = result["Action"].unique()
            print(f"  {icon} {test['name']}")
            print(f"         Expected: {test['expect']} | Actual: {', '.join(actual_actions)}")
        else:
            print(f"  {icon} {test['name']}")

    print(f"\n  Result: {passed}/{len(REACHABILITY_TESTS)} tests passed, {failed} failed")
    return failed == 0


def main():
    bf = init_session()

    load_snapshot(bf, GOOD_SNAPSHOT_PATH, GOOD_SNAPSHOT_NAME)
    good_ok = run_reachability_tests(bf, "Good Network")

    load_snapshot(bf, BAD_SNAPSHOT_PATH, BAD_SNAPSHOT_NAME)
    bad_ok = run_reachability_tests(bf, "Bad Network (with bugs)")

    print_section("Summary")
    check_result(good_ok, "Good network: all reachability tests pass",
                 "Good network: some tests FAILED (unexpected)")
    check_result(not bad_ok, "Bad network: bugs detected by reachability tests",
                 "Bad network: bugs NOT detected (tests should have failed)")


if __name__ == "__main__":
    main()
