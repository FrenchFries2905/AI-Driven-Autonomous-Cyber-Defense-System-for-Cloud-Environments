#!/bin/sh
# Port scan of the victim (a "Probe" attack).
# Usage: portscan.sh [max_probes_per_second]    default 100
RATE="${1:-100}"
echo "Port scan: ports 1-1000, up to ${RATE} probes per second, target: victim"
nmap -sS -p 1-1000 --max-rate "$RATE" -n victim
