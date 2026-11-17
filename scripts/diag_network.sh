#!/usr/bin/env bash
# Netzwerk-Diagnose WSL -> mcp.galaxus.ch. Ergebnis in output/diag.log (nicht im Repository).
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p output
LOG=output/diag.log
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"diag","version":"0.1"}}}'
FMT='HTTP %{http_code}, %{time_total}s, IP %{remote_ip}\n'
{
  echo "Lauf $(date -Is)"
  echo "== DNS"; getent ahosts mcp.galaxus.ch | head -4
  echo "== GET README (Standard)"; curl -s -o /dev/null -m 40 -w "$FMT" https://mcp.galaxus.ch/static/README.md
  echo "== POST initialize (Standard)"; curl -s -o /dev/null -m 40 -w "$FMT" -X POST https://mcp.galaxus.ch/ \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d "$INIT"
  echo "== POST initialize (nur IPv4)"; curl -4 -s -o /dev/null -m 40 -w "$FMT" -X POST https://mcp.galaxus.ch/ \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d "$INIT"
  echo "== POST initialize (HTTP/1.1)"; curl --http1.1 -s -o /dev/null -m 40 -w "$FMT" -X POST https://mcp.galaxus.ch/ \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d "$INIT"
} 2>&1 | tee "$LOG"
