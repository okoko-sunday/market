#!/bin/sh
set -eu
origin="${1:-http://localhost:8002}"
i=0
while [ "$i" -lt 100 ]; do
  curl -fsS "$origin/api/v1/vehicles/?page_size=24&availability=available" >/dev/null
  i=$((i+1))
done
echo "Completed 100 bounded catalog requests"
