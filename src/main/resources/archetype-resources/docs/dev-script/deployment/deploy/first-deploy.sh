#set( $dollar = '$' )
#set( $hash = '#' )
${hash}!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${dollar}(cd -- "${dollar}(dirname -- "${dollar}0")" && pwd)"
python3 "${dollar}SCRIPT_DIR/../lib/host.py" prepare --root /opt/${artifactId} --fix "${dollar}@"
exec python3 "${dollar}SCRIPT_DIR/../lib/server.py" deploy-first "${dollar}@"
