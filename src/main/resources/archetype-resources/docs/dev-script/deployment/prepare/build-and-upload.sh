#set( $dollar = '$' )
#set( $hash = '#' )
${hash}!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="${dollar}(cd -- "${dollar}(dirname -- "${dollar}0")" && pwd)"
exec python3 "${dollar}SCRIPT_DIR/build_upload.py" "${dollar}@"
