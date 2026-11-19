#!/bin/sh
# Shared helpers for the attack scripts.
# Every attack appends one line to /data/attack_windows.csv: start,end,label,attack
# That file is how recorded flows get their ground-truth labels for retraining.

WINDOWS_FILE=/data/attack_windows.csv

now() { date +%s.%N; }

log_window() {
  # usage: log_window <class label> <attack name> <start time>
  if [ ! -d /data ]; then
    echo "note: /data is not mounted, so this attack was not recorded for retraining"
    return 0
  fi
  [ -s "$WINDOWS_FILE" ] || echo "start,end,label,attack" > "$WINDOWS_FILE"
  echo "$3,$(now),$1,$2" >> "$WINDOWS_FILE"
}
