#!/usr/bin/env bash
# run_tests.sh – build the virtual lab, run the drift playbook, show results.
#
# Usage:
#   ./lab/run_tests.sh            # start lab + run playbook + stop lab
#   ./lab/run_tests.sh --keep-up  # keep containers running after the test

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB_DIR="${REPO_ROOT}/lab"
KEEP_UP=false

for arg in "$@"; do
  [[ "$arg" == "--keep-up" ]] && KEEP_UP=true
done

# ── helpers ──────────────────────────────────────────────────────────────────
info()  { echo "[INFO]  $*"; }
ok()    { echo "[OK]    $*"; }
warn()  { echo "[WARN]  $*"; }
die()   { echo "[ERROR] $*" >&2; exit 1; }

# ── pre-flight checks ─────────────────────────────────────────────────────────
command -v docker      >/dev/null 2>&1 || die "docker is not installed."
command -v ansible-playbook >/dev/null 2>&1 || die "ansible-playbook is not installed."

info "Checking Ansible collections..."
if ! ansible-galaxy collection list cisco.ios 2>/dev/null | grep -q cisco.ios; then
  info "Installing required collections..."
  ansible-galaxy collection install -r "${REPO_ROOT}/requirements.yml"
fi

# ── start the lab ─────────────────────────────────────────────────────────────
info "Building and starting virtual lab containers..."
cd "${LAB_DIR}"
docker compose up -d --build

info "Waiting for SSH services to become ready..."
READY=0
for attempt in $(seq 1 20); do
  if docker compose ps | grep -qE "(healthy|Up)" && \
     nc -z 127.0.0.1 2221 2>/dev/null && \
     nc -z 127.0.0.1 2222 2>/dev/null && \
     nc -z 127.0.0.1 2223 2>/dev/null; then
    READY=1
    break
  fi
  echo "  ...waiting (${attempt}/20)"
  sleep 2
done

if [[ $READY -eq 0 ]]; then
  # nc might not be installed – try a simple python fallback
  for port in 2221 2222 2223; do
    python3 -c "
import socket, sys, time
for _ in range(10):
    try:
        s = socket.create_connection(('127.0.0.1', ${port}), timeout=2)
        s.close(); sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit(1)
" || die "Port ${port} did not become available in time."
  done
fi
ok "All three mock routers are up."

# ── run the playbook ──────────────────────────────────────────────────────────
cd "${REPO_ROOT}"
info "Running detect_drift.yml against the virtual lab..."
echo ""
ansible-playbook playbooks/detect_drift.yml -v
echo ""

# ── show drift reports ────────────────────────────────────────────────────────
info "Drift reports written to ./drift_reports/"
for report in drift_reports/*.txt; do
  [[ -f "$report" ]] || continue
  echo ""
  echo "══════════════════════════════════════════════"
  echo " $report"
  echo "══════════════════════════════════════════════"
  cat "$report"
done

if [[ -f drift_reports/drift_detection.log ]]; then
  echo ""
  info "Detection log (drift_reports/drift_detection.log):"
  cat drift_reports/drift_detection.log
fi

# ── tear down ─────────────────────────────────────────────────────────────────
if [[ "$KEEP_UP" == "false" ]]; then
  info "Stopping virtual lab containers..."
  cd "${LAB_DIR}"
  docker compose down
  ok "Lab stopped."
else
  warn "Containers left running (--keep-up). Stop with: cd lab && docker compose down"
fi

ok "Done."
