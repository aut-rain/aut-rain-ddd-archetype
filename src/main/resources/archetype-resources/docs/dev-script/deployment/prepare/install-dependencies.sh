#set( $dollar = '$' )
#set( $hash = '#' )
${hash}!/usr/bin/env bash
set -euo pipefail
if [[ "${dollar}{1:-}" != --execute ]]; then
  echo 'Ubuntu apt installation plan: python3 docker.io docker-compose-v2 curl ca-certificates openssh-client iproute2 tar coreutils'
  echo 'Run with --execute as root to install. Package installation may start Docker.'
  exit 0
fi
[[ ${dollar}${hash} = 1 && ${dollar}EUID = 0 ]] || { echo 'Use sudo bash install-dependencies.sh --execute' >&2; exit 2; }
. /etc/os-release
[[ "${dollar}ID" = ubuntu ]] || { echo 'Automatic installation supports Ubuntu only; install Python 3.10+, Docker Engine and Compose 2.24+ using your distribution documentation.' >&2; exit 2; }
${hash} Avoid replacing an existing Docker CE/Desktop installation.
if command -v docker >/dev/null; then
  echo 'Docker already installed; retain its package source and install missing dependencies manually.' >&2
  exit 2
fi
apt-get update
apt-cache show docker-compose-v2 >/dev/null
apt-get install -y python3 docker.io docker-compose-v2 curl ca-certificates openssh-client iproute2 tar coreutils
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python >= 3.10 required"'
docker compose version
printf '%s\n' 'Rerun server-preflight.sh. This script does not enable/start application services.'
