#!/bin/sh
# Port scan of the victim (a "Probe" attack).
# Usage: portscan.sh [max_probes_per_second]    default 100
. /attacks/lib.sh
RATE="${1:-100}"
echo "Port scan: ports 1-1000, up to ${RATE} probes per second, target: victim"
T0=$(now)
nmap -sS -p 1-1000 --max-rate "$RATE" -n victim
log_window Probe portscan "$T0"
