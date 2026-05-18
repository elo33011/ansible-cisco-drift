# Batfish Network Configuration Management Demo

This project demonstrates how [Batfish](https://www.batfish.org/) — an open-source network configuration analysis tool — helps network engineers **validate, audit, and manage configurations without ever touching a live device**.

## What is Batfish?

Batfish parses device configurations (Cisco IOS/NX-OS, Juniper JunOS, Arista EOS, and more), builds a complete mathematical model of the network, and lets you query it with Python.

| Capability | Description |
|---|---|
| **Reachability verification** | Can host A reach host B? What path does traffic take? |
| **Security policy auditing** | What does this ACL actually permit or deny? Any shadowed rules? |
| **Configuration error detection** | Routing black holes, OSPF mismatches, undefined references |
| **Pre-change impact analysis** | What traffic breaks if I change this route/ACL? |
| **Configuration consistency** | Are all devices configured consistently? |

**Key advantage**: All analysis runs entirely offline against config files. No agents on devices. No production risk.

---

## Demo Network Topology

```
           Internet (203.0.113.0/30)
                   |
             [firewall-01]
            /              \
   [core-router-01]    [core-router-02]   <- iBGP AS 65001 + OSPF Area 0
       /     \               /     \
 [dist-sw-01]  --------  [dist-sw-02]
       |
 [access-sw-01]
   /      \      \
 Users   Users  Servers
```

### Address Space

| Network | Role |
|---|---|
| `10.10.10.0/24` | Server VLAN |
| `10.20.20.0/24` | User VLAN |
| `10.100.100.0/24` | Management VLAN |
| `10.0.x.x/30` | Routing links between devices |
| `10.255.x.x/32` | Loopback addresses |
| `203.0.113.0/30` | Internet uplink |

---

## Two Snapshots: Good vs Bad

| Snapshot | Description |
|---|---|
| `snapshots/good-network/` | Correctly configured baseline |
| `snapshots/bad-network/` | Same network with **4 intentional bugs** |

### The 4 Intentional Bugs (that Batfish detects)

1. **Black hole route** on `core-router-01`: Static route sends `10.10.10.0/24` to `Null0`, silently dropping all server traffic
2. **Shadowed ACL rules** on `dist-switch-01`: The `deny` rule appears *before* the `permit` rules — blocking ALL traffic to the server VLAN
3. **Inconsistent ACL** on `dist-switch-02`: Missing the management SSH permit rule (different policy from dist-switch-01)
4. **Firewall security hole** on `firewall-01`: WAN ACL permits all internet traffic before any deny rules (IP spoofing vulnerability)

---

## Demo Scripts

| Script | Batfish Questions Used |
|---|---|
| `01_topology_exploration.py` | `nodeProperties`, `interfaceProperties`, `layer3Edges`, `ospfSessionCompatibility` |
| `02_reachability_analysis.py` | `reachability`, `traceroute` |
| `03_routing_analysis.py` | `routes`, `traceroute`, `detectLoops` |
| `04_acl_analysis.py` | `filterLineReachability`, `searchFilters` |
| `05_config_consistency.py` | `ospfSessionCompatibility`, `bgpSessionCompatibility`, `undefinedReferences` |
| `06_change_impact_analysis.py` | `differentialReachability` |

---

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Start Batfish server + Jupyter Lab
docker-compose up -d

# Open notebook: http://localhost:8888  (token: batfish-demo)
# Batfish API:   http://localhost:9997
```

### Option 2: Scripts Only

```bash
# 1. Start Batfish server
docker run -d --name batfish \
  -p 9997:9997 -p 9996:9996 \
  batfish/allinone:latest

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Run all demos
cd scripts && bash run_all.sh
```

### Option 3: Run Scripts Individually

```bash
cd scripts
python 01_topology_exploration.py
python 02_reachability_analysis.py
python 03_routing_analysis.py
python 04_acl_analysis.py
python 05_config_consistency.py
python 06_change_impact_analysis.py
```

## Prerequisites

- Docker & Docker Compose
- Python 3.8+
- ~4 GB RAM for the Batfish container

## How Batfish Works Internally

```
Config Files ──> Batfish Server ──> Data Plane Model ──> Query Results
(Cisco IOS,       (Java/Docker,       (Complete routing      (pandas
 Juniper, etc.)    offline)            + forwarding)          DataFrames)
```

## Real-World Use Cases

- **CI/CD pre-validation**: Run Batfish against candidate configs before pushing to devices
- **Security audits**: Verify firewall/ACL policies match security requirements automatically
- **Change management**: Quantify the exact blast radius of any proposed change
- **Configuration drift**: Compare snapshots over time to catch unauthorized changes
- **Documentation**: Auto-generate accurate topology and routing documentation
