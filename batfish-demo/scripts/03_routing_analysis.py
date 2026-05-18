#!/usr/bin/env python3
"""
Demo 03: Routing Analysis

Inspects routing tables, traces forwarding paths hop-by-hop, and
detects routing black holes and loops. Batfish's traceroute is
equivalent to doing a traceroute across a virtual copy of your network.
"""

import sys
sys.path.insert(0, '.')
from common import *
from pybatfish.datamodel.flow import HeaderConstraints


def show_routing_tables(bf):
    print_section("Routing Tables (Core Routers)")
    routes = bf.q.routes(
        nodes="core-router-01|core-router-02",
        network="10.10.10.0/24"
    ).answer().frame()

    if len(routes) == 0:
        print("No routes found for 10.10.10.0/24!")
    else:
        cols = [c for c in ["Node", "Network", "Protocol", "Next_Hop_IP",
                             "Next_Hop_Interface", "Admin_Distance", "Metric"]
                if c in routes.columns]
        print(routes[cols].to_string(index=False))

        null_routes = routes[
            routes.get("Next_Hop_Interface", "").astype(str).str.contains("Null", na=False)
        ]
        if len(null_routes) > 0:
            print(f"\nWARNING: {len(null_routes)} NULL/black-hole route(s) for server subnet!")
            print(null_routes[cols].to_string(index=False))


def trace_path(bf):
    print_section("Forwarding Path Trace: User (10.20.20.100) -> Server (10.10.10.50) HTTPS")
    result = bf.q.traceroute(
        startLocation="@enter(dist-switch-01[Vlan20])",
        headers=HeaderConstraints(
            srcIps="10.20.20.100",
            dstIps="10.10.10.50",
            ipProtocols=["TCP"],
            dstPorts=["443"],
        ),
    ).answer().frame()

    if len(result) == 0:
        print("No traceroute results.")
        return

    for _, row in result.iterrows():
        flow = row.get("Flow", "")
        traces = row.get("Traces", [])
        print(f"Flow: {flow}")
        if traces:
            for trace in list(traces)[:2]:  # Show up to 2 ECMP paths
                print(f"  Disposition: {trace.disposition}")
                for i, hop in enumerate(trace.hops):
                    node = hop.node
                    steps = [str(s.action) for s in hop.steps]
                    print(f"    Hop {i+1}: {node} -> {' -> '.join(steps)}")


def detect_black_holes(bf):
    print_section("Detecting Routing Black Holes")
    result = bf.q.routes(network="10.10.10.0/24").answer().frame()
    if len(result) == 0:
        print("No routes to 10.10.10.0/24 found anywhere in the network.")
        return

    null_col = "Next_Hop_Interface" if "Next_Hop_Interface" in result.columns else None
    if null_col:
        null_routes = result[result[null_col].astype(str).str.contains("Null|null", na=False)]
        if len(null_routes) > 0:
            print(f"CRITICAL: {len(null_routes)} black-hole routes detected!")
            cols = [c for c in ["Node", "Network", null_col, "Protocol"] if c in null_routes.columns]
            print(null_routes[cols].to_string(index=False))
        else:
            print("No black-hole routes found.")
    else:
        print("Could not determine next-hop interface column.")
        print(result.columns.tolist())


def detect_loops(bf):
    print_section("Detecting Routing Loops")
    loops = bf.q.detectLoops().answer().frame()
    if len(loops) == 0:
        print("No routing loops detected.")
    else:
        print(f"WARNING: {len(loops)} routing loops found!")
        print(loops.to_string(index=False))


def main():
    bf = init_session()

    print("\n" + "#" * 65)
    print("  GOOD NETWORK")
    print("#" * 65)
    load_snapshot(bf, GOOD_SNAPSHOT_PATH, GOOD_SNAPSHOT_NAME)
    show_routing_tables(bf)
    trace_path(bf)
    detect_black_holes(bf)
    detect_loops(bf)

    print("\n" + "#" * 65)
    print("  BAD NETWORK — Expect: black hole on core-router-01")
    print("#" * 65)
    load_snapshot(bf, BAD_SNAPSHOT_PATH, BAD_SNAPSHOT_NAME)
    show_routing_tables(bf)
    trace_path(bf)
    detect_black_holes(bf)
    detect_loops(bf)


if __name__ == "__main__":
    main()
