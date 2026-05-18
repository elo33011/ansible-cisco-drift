#!/usr/bin/env python3
"""
Demo 05: Configuration Consistency Checks

Checks for inconsistencies and errors across all device configurations:
  - OSPF session mismatches (area, timer, auth inconsistencies)
  - BGP session compatibility
  - Undefined references (ACLs applied but not defined)
  - Unused structures (ACLs defined but never applied)
  - Duplicate IP addresses

This is useful for detecting configuration drift in large networks.
"""

import sys
sys.path.insert(0, '.')
from common import *


def check_ospf(bf):
    print_section("OSPF Session Compatibility")
    ospf = bf.q.ospfSessionCompatibility().answer().frame()
    if len(ospf) == 0:
        print("  No OSPF sessions found.")
        return

    established = ospf[ospf["Session_Status"] == "ESTABLISHED"]
    broken = ospf[ospf["Session_Status"] != "ESTABLISHED"]
    print(f"  Established: {len(established)}")
    print(f"  Broken:      {len(broken)}")

    if len(broken) > 0:
        print("\n  BROKEN SESSIONS:")
        cols = [c for c in ["Interface", "Remote_Interface", "Session_Status"]
                if c in broken.columns]
        print(broken[cols].to_string(index=False))
    else:
        print("  All OSPF sessions are compatible.")


def check_bgp(bf):
    print_section("BGP Session Compatibility")
    try:
        bgp = bf.q.bgpSessionCompatibility().answer().frame()
    except Exception as e:
        print(f"  BGP compatibility check not available: {e}")
        return

    if len(bgp) == 0:
        print("  No BGP sessions found.")
        return

    bad_col = next((c for c in bgp.columns if "Status" in c or "Established" in c), None)
    if bad_col:
        issues = bgp[bgp[bad_col] != "ESTABLISHED"]
        if len(issues) > 0:
            print(f"  WARNING: {len(issues)} BGP issues detected.")
            print(issues.to_string(index=False))
        else:
            print(f"  All {len(bgp)} BGP sessions are compatible.")
    else:
        print(bgp.to_string(index=False))


def check_undefined_references(bf):
    print_section("Undefined References")
    try:
        refs = bf.q.undefinedReferences().answer().frame()
    except Exception as e:
        print(f"  undefinedReferences not available: {e}")
        return

    if len(refs) == 0:
        print("  No undefined references.")
    else:
        print(f"  WARNING: {len(refs)} undefined references found!")
        cols = [c for c in ["Nodes", "Type", "Name", "Usage"] if c in refs.columns]
        print(refs[cols].to_string(index=False))


def check_unused_structures(bf):
    print_section("Unused Structures (ACLs, Prefix-lists, etc.)")
    try:
        unused = bf.q.unusedStructures().answer().frame()
    except Exception as e:
        print(f"  unusedStructures not available: {e}")
        return

    if len(unused) == 0:
        print("  No unused structures found.")
    else:
        print(f"  Found {len(unused)} unused structure(s):")
        cols = [c for c in ["Nodes", "Type", "Name", "Filename"] if c in unused.columns]
        print(unused[cols].to_string(index=False))


def check_ip_conflicts(bf):
    print_section("IP Address Conflicts")
    ifaces = bf.q.interfaceProperties(
        properties="Interface,Primary_Address,Active"
    ).answer().frame()
    active = ifaces[ifaces["Active"] == True]
    ips = active["Primary_Address"].dropna()
    duplicates = ips[ips.duplicated(keep=False)]
    if len(duplicates) == 0:
        print("  No duplicate IP addresses.")
    else:
        print(f"  WARNING: {len(duplicates)} duplicate IP addresses!")
        dup_ifaces = active[active["Primary_Address"].isin(duplicates)]
        print(dup_ifaces[["Interface", "Primary_Address"]].to_string(index=False))


def main():
    bf = init_session()

    print("\n" + "#" * 65)
    print("  GOOD NETWORK")
    print("#" * 65)
    load_snapshot(bf, GOOD_SNAPSHOT_PATH, GOOD_SNAPSHOT_NAME)
    check_ospf(bf)
    check_bgp(bf)
    check_undefined_references(bf)
    check_unused_structures(bf)
    check_ip_conflicts(bf)

    print("\n" + "#" * 65)
    print("  BAD NETWORK")
    print("#" * 65)
    load_snapshot(bf, BAD_SNAPSHOT_PATH, BAD_SNAPSHOT_NAME)
    check_ospf(bf)
    check_bgp(bf)
    check_undefined_references(bf)
    check_unused_structures(bf)
    check_ip_conflicts(bf)


if __name__ == "__main__":
    main()
