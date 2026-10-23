#!/bin/sh
# Ordinary web browsing against the victim: one request every 0.5 to 2.5 seconds.
while true; do
  curl -s -o /dev/null --max-time 5 http://victim/ < /dev/null
  sleep "$(awk 'BEGIN{srand(); printf "%.2f", 0.5 + rand() * 2}')"
done
