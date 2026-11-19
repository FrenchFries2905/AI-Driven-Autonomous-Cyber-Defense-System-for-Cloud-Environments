#!/bin/sh
# A labeled capture session for retraining: two rounds of every attack, quiet periods in between.
# Takes about 6 minutes with the default 40 s pauses. Afterwards run:  python -m src.model.retrain
# Usage: session.sh [pause_seconds]
WAIT="${1:-40}"
for round in 1 2; do
  echo "=== round $round: port scan ==="
  sh /attacks/portscan.sh 100
  echo "quiet for ${WAIT}s"; sleep "$WAIT"
  echo "=== round $round: SYN flood, single port ==="
  sh /attacks/synflood.sh 15 5000
  echo "quiet for ${WAIT}s"; sleep "$WAIT"
  echo "=== round $round: SYN flood, random ports and sources ==="
  sh /attacks/synflood_random.sh 15 5000
  echo "quiet for ${WAIT}s"; sleep "$WAIT"
done
echo "=== session finished ==="
