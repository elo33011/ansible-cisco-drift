#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "======================================================="
echo "  Batfish Network Configuration Management Demo"
echo "======================================================="
echo ""
echo "Make sure Batfish is running: docker-compose up -d batfish"
echo ""

scripts=(
    "01_topology_exploration.py"
    "02_reachability_analysis.py"
    "03_routing_analysis.py"
    "04_acl_analysis.py"
    "05_config_consistency.py"
    "06_change_impact_analysis.py"
)

for script in "${scripts[@]}"; do
    echo ""
    echo "-------------------------------------------------------"
    echo "  Running: $script"
    echo "-------------------------------------------------------"
    python "$script"
done

echo ""
echo "======================================================="
echo "  All demos complete!"
echo "======================================================="
