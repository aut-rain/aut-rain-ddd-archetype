#set( $dollar = '$' )
#set( $hash = '#' )
"""Read-only local build/SSH prerequisite check; does not connect to a server."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from delivery import deployment_sources

failed = []
try:
    sources = deployment_sources(ROOT)
    print('OK: deployment sources, including backend Dockerfile, Nginx and middleware (' + str(len(sources)) + ' files)')
except (OSError, ValueError) as error:
    print('FAIL: ' + str(error))
    failed.append('deployment sources')
for name in ('python', 'node', 'corepack', 'mvn', 'git', 'ssh', 'scp'):
    found = shutil.which(name + '.cmd') or shutil.which(name)
    print(('OK: ' if found else 'FAIL: ') + name)
    if not found:
        failed.append(name)
try:
    node = subprocess.check_output(['node', '--version'], text=True).strip()
    if node != 'v22.22.0':
        raise ValueError('Node.js must be 22.22.0')
    if sys.version_info < (3, 12):
        raise ValueError('Local packaging requires Python >= 3.12')
    expected = json.loads((ROOT / 'web/package.json').read_text())['packageManager'].split('@')[1]
    print('Required pnpm (via Corepack): ' + expected + '; Java 21 and Maven 3.9+ required')
except (OSError, ValueError, subprocess.SubprocessError) as error:
    print('FAIL: ' + str(error))
    failed.append('versions')
ssh = Path.home() / '.ssh'
print('SSH public keys found: ' + str(len(list(ssh.glob('*.pub')))))
print('SSH known_hosts exists: ' + str((ssh / 'known_hosts').is_file()))
print('Keys are optional with password authentication; private key contents are never printed.')
for name in ('app-backend/${artifactId}-app/target/${artifactId}-app.jar', 'web/dist/index.html'):
    print(('OK: ' if (ROOT / name).is_file() else 'WARN: build required: ') + name)
sys.exit(1 if failed else 0)
