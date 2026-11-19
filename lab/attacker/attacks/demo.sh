#!/bin/sh
# Full demo: quiet period, then a port scan, then a SYN flood over many ports.
echo "=== 1/3 quiet period (10s): only benign traffic ==="
sleep 10
echo "=== 2/3 port scan ==="
sh /attacks/portscan.sh 100
sleep 5
echo "=== 3/3 SYN flood (15s) ==="
sh /attacks/synflood_random.sh 15 5000
echo "=== demo finished ==="
