#set( $dollar = '$' )
#set( $hash = '#' )
${hash}!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=${dollar}(cd -- "${dollar}(dirname -- "${dollar}0")" && pwd)
INTERVAL=60
ONCE=0
ROOT=/opt/${artifactId}
ARGS=()
while ((${dollar}${hash})); do
  case "${dollar}1" in
    --interval) INTERVAL=${dollar}{2:?missing value for --interval}; shift 2 ;;
    --once) ONCE=1; shift ;;
    --root) ROOT=${dollar}{2:?missing root}; ARGS+=("--root" "${dollar}ROOT"); shift 2 ;;
    *) ARGS+=("${dollar}1"); shift ;;
  esac
done
[[ "${dollar}INTERVAL" =~ ^[1-9][0-9]*${dollar} ]] || { echo 'interval must be a positive number of seconds' >&2; exit 2; }
while :; do
  printf '\n[%s] ${artifactId} monitor\n' "${dollar}(date --iso-8601=seconds 2>/dev/null || date)"
  SERVER="${dollar}ROOT/current/lib/server.py"
  [[ -f "${dollar}SERVER" ]] || { echo "No successful current release" >&2; exit 1; }
  if python3 "${dollar}SERVER" verify "${dollar}{ARGS[@]}"; then
    python3 "${dollar}SERVER" status "${dollar}{ARGS[@]}"
  else
    printf 'Health check failed; inspect logs before taking action.\n' >&2
    python3 "${dollar}SERVER" logs "${dollar}{ARGS[@]}" || true
    ((ONCE)) && exit 1
  fi
  ((ONCE)) && exit 0
  sleep "${dollar}INTERVAL"
done
