#!/usr/bin/env python3
"""
Demo 01: Network Topology Exploration

Batfish automatically parses device configs and builds a complete
network model. This script explores that model: devices, interfaces,
L3 topology, OSPF sessions, and BGP peers.
"""

import sys
sys.path.insert(0, '.')
from common import *


def explore_topology(bf):
    print_section("1. Discovered Network Devices")
    nodes = bf.q.nodeProperties(
        properties="Configuration_Format"
    ).answer().frame()
    print(f"Total devices discovered: {len(nodes)}")
    print(nodes[["Node", "Configuration_Format"]].to_string(index=False))

    print_section("2. Active Network Interfaces")
    ifaces = bf.q.interfaceProperties(
        properties="Interface,Primary_Address,Active,Description"
    ).answer().frame()
    active = ifaces[ifaces["Active"] == True]
    print(f"Active interfaces: {len(active)}")
    print(active[["Interface", "Primary_Address", "Description"]].to_string(index=False))

    print_section("3. Layer-3 Topology (Routing Adjacencies)")
    edges = bf.q.layer3Edges().answer().frame()
    print(f"L3 edges: {len(edges)}")
    if len(edges) > 0:
        print(edges[["Interface", "Remote_Interface"]].to_string(index=False))

    print_section("4. OSPF Session Status")
    ospf = bf.q.ospfSessionCompatibility().answer().frame()
    if len(ospf) == 0:
        print("No OSPF sessions found.")
    else:
        established = ospf[ospf["Session_Status"] == "ESTABLISHED"]
        broken = ospf[ospf["Session_Status"] != "ESTABLISHED"]
        print(f"  Established: {len(established)}")
        print(f"  Broken:      {len(broken)}")
        print()
        print(ospf[["Interface", "Remote_Interface", "Session_Status"]].to_string(index=False))
        if len(broken) > 0:
            print(f"\nWARNING: {len(broken)} broken OSPF sessions detected!")
            print(broken[["Interface", "Remote_Interface", "Session_Status"]].to_string(index=False))

    print_section("5. BGP Peer Configuration")
    bgp = bf.q.bgpPeerConfiguration().answer().frame()
    if len(bgp) == 0:
        print("No BGP peers configured.")
    else:
        print(bgp[["Node", "Local_AS", "Remote_AS", "Remote_IP", "Description"]].to_string(index=False))

    print_section("6. Config Parse Warnings")
    warnings = bf.q.parseWarning().answer().frame()
    if len(warnings) == 0:
        print("No parse warnings — all configs parsed cleanly.")
    else:
        print(f"WARNING: {len(warnings)} parse issues found:")
        print(warnings.to_string(index=False))


def main():
    bf = init_session()

    print("\n" + "#" * 65)
    print("  GOOD NETWORK - Expected: clean topology, all sessions up")
    print("#" * 65)
    load_snapshot(bf, GOOD_SNAPSHOT_PATH, GOOD_SNAPSHOT_NAME)
    explore_topology(bf)

    print("\n" + "#" * 65)
    print("  BAD NETWORK  - Expected: issues in topology/sessions")
    print("#" * 65)
    load_snapshot(bf, BAD_SNAPSHOT_PATH, BAD_SNAPSHOT_NAME)
    explore_topology(bf)


if __name__ == "__main__":
    main()
