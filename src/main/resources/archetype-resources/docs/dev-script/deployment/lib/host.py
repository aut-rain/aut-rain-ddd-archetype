#set( $dollar = '$' )
#set( $hash = '#' )
"""Host inspection and explicitly requested remediation; no implicit cleanup."""
import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = '${artifactId}'
LABEL = 'com.docker.compose.project'
MARKER = '.${artifactId}-managed'
WEB_ROOT = Path('/var/www/${artifactId}')


def root_path(value):
    path = Path(value)
    resolved = path.resolve()
    if not path.is_absolute() or path != resolved or len(path.parts) < 3:
        raise ValueError('Use a canonical absolute application directory, without symlinks or ..')
    if resolved in (Path('/'), Path('/opt'), Path('/var'), Path('/var/lib'), Path('/usr/local'), Path('/home'), Path('/tmp')):
        raise ValueError('Refusing a shared system directory')
    return resolved


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).strip()


def inventory():
    result = {}
    for kind, command in [('containers', ['docker', 'ps', '-aq']),
                          ('volumes', ['docker', 'volume', 'ls', '-q']),
                          ('networks', ['docker', 'network', 'ls', '-q'])]:
        ids = run(*command, '--filter', 'label=' + LABEL + '=' + PROJECT).splitlines()
        inspect = ['docker', 'inspect'] if kind == 'containers' else ['docker', kind[:-1], 'inspect']
        result[kind] = json.loads(run(*inspect, *ids)) if ids else []
    return result


def ownership(root, create=False):
    for name in ('releases', 'backups', '.env', '.deployment.lock', 'active.json', 'previous-release.txt'):
        if (root / name).is_symlink():
            raise ValueError('Refusing symlink: ' + name)

    marker = root / MARKER
    if marker.is_symlink():
        raise ValueError('Managed marker cannot be a symlink')
    if marker.exists():
        if marker.read_text().strip() != PROJECT:
            raise ValueError('Invalid managed-directory marker')
    elif create:
        if root.exists():
            allowed = {MARKER, 'releases', 'backups', '.env', '.deployment.lock', 'current',
                       'active.json', 'previous-release.txt'}
            require(all(p.name in allowed for p in root.iterdir()), 'Unknown contents: refusing to adopt this root')
        root.mkdir(parents=True, exist_ok=True)
        marker.write_text(PROJECT + '\n')
    else:
        raise ValueError('Run prepare-server.sh --fix for this project root first')


def web_ownership(create=False):
    if WEB_ROOT.is_symlink():
        raise ValueError('Frontend root cannot be a symlink')
    marker = WEB_ROOT / MARKER
    if marker.is_symlink():
        raise ValueError('Frontend marker cannot be a symlink')
    if marker.exists():
        require(marker.read_text().strip() == PROJECT, 'Invalid frontend managed-directory marker')
    elif create:
        if WEB_ROOT.exists():
            allowed = {MARKER, 'releases', 'current'}
            require(all(p.name in allowed for p in WEB_ROOT.iterdir()), 'Unknown frontend contents: refusing to adopt this root')
        WEB_ROOT.mkdir(parents=True, exist_ok=True)
        marker.write_text(PROJECT + '\n')
    else:
        raise ValueError('Run prepare-server.sh --fix for the frontend root first')
    for name in ('releases', 'current'):
        require(not (WEB_ROOT / name).is_symlink() or name == 'current', 'Refusing frontend symlink: ' + name)


@contextlib.contextmanager
def locked(root):
    import fcntl
    ownership(root)
    with (root / '.deployment.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def preflight(root, release=None, port=${httpPort}, mode='first'):
    from server import configuration
    from delivery import verify_release
    failed = []
    def check(name, operation):
        try:
            info = operation()
            print('OK: ' + name + (': ' + str(info) if isinstance(info, (str, int)) else ''))
            return info
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            ${hash} Do not echo command stderr/config values, which may contain secrets.
            print('FAIL: ' + name + ' (' + type(error).__name__ + ')')
            failed.append(name)
            return None
    def version():
        text = run('docker', 'compose', 'version', '--short')
        numbers = re.search(r'(\d+)\.(\d+)', text)
        if not numbers or tuple(map(int, numbers.groups())) < (2, 24):
            raise ValueError('Compose >= 2.24 required')
        return text
    check('Python >= 3.10', lambda: require(sys.version_info >= (3, 10), 'Python too old'))
    check('Docker daemon and permissions', lambda: run('docker', 'info', '--format', '{{.ServerVersion}}'))
    check('Docker Compose >= 2.24', version)
    check('port inspection command ss', lambda: require(shutil.which('ss'), 'Install iproute2'))
    for name in ('tar', 'sha256sum', 'curl'):
        check('command ' + name, lambda name=name: require(shutil.which(name), 'Missing tool'))
    print('INFO: SSH transport uses host OpenSSH authentication. No application JWT/TLS keys are required for this HTTP deployment.')
    print('INFO: inherited database secrets are ignored; server configuration comes from root/.env.')
    config = check('server .env (keys, passwords, mode)', lambda: configuration(root))
    ${hash} Never print secrets returned by configuration.
    if config:
        port = int(config['HTTP_PORT'])
    def access():
        require(root.is_dir() and os.access(root, os.R_OK | os.W_OK | os.X_OK), 'Root missing/not writable')
        for name in ('releases', 'backups'):
            folder = root / name
            require(folder.is_dir() and os.access(folder, os.R_OK | os.W_OK | os.X_OK), 'Directory missing/not writable')
        ownership(root)
        web_ownership()
        require(WEB_ROOT.is_dir() and os.access(WEB_ROOT, os.R_OK | os.W_OK | os.X_OK), 'Frontend root missing/not writable')
        require((WEB_ROOT / 'releases').is_dir(), 'Frontend releases directory missing')
        return 'backend and frontend roots are managed, readable and writable'
    check('directories and permissions', access)
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    free = shutil.disk_usage(ancestor).free
    check('at least 2 GiB free disk', lambda: require(free >= 2 * 1024**3, 'Insufficient free disk'))
    resources = check('project resources inventory', lambda: inventory())
    if resources is not None:
        print('INFO: project containers=%d volumes=%d networks=%d' % tuple(len(resources[k]) for k in ('containers', 'volumes', 'networks')))
        if mode == 'first':
            check('no previous project data/containers', lambda: require(not resources['containers'] and not resources['volumes'] and not (root / 'current').exists() and not (root / 'active.json').exists(), 'Existing deployment residue'))
        def state_check():
            path = root / 'active.json'
            if path.exists():
                state = json.loads(path.read_text())
                return str(state.get('status')) + ', release=' + str(state.get('release'))
            return 'none'
        check('deployment state (deploying means recovery required)', state_check)
        def port_check():
            listeners = run('ss', '-ltnH', 'sport = :' + str(port))
            owners = [c for c in resources['containers'] if c.get('State', {}).get('Running') and
                      c.get('Config', {}).get('Labels', {}).get('com.docker.compose.service') == 'nginx' and
                      any(p.get('HostPort') == str(port) for bindings in c.get('NetworkSettings', {}).get('Ports', {}).values() for p in (bindings or []))]
            running_ids = run('docker', 'ps', '-q').split()
            published = json.loads(run('docker', 'inspect', *running_ids)) if running_ids else []
            other = [c for c in published if c.get('Config', {}).get('Labels', {}).get(LABEL) != PROJECT and
                     any(p.get('HostPort') == str(port) for bindings in c.get('NetworkSettings', {}).get('Ports', {}).values() for p in (bindings or []))]
            require(not other and (not listeners or (mode == 'update' and len(owners) == 1)), 'Port occupied by another service')
            return str(port) + (' owned by project nginx' if owners else ' available')
        check('HTTP port', port_check)
    if release:
        def payload():
            manifest = verify_release(release)
            require(release.resolve().parent == root / 'releases', 'Release outside managed root')
            require((WEB_ROOT / 'releases').is_dir() and os.access(WEB_ROOT / 'releases', os.W_OK),
                    'Frontend release destination is missing or not writable')
            return manifest['release_id']
        check('pending release checksums/JAR/frontend/migrations', payload)
        if config:
            from server import Deployment
            import server
            original = server.RELEASE
            try:
                server.RELEASE = release.resolve()
                check('Compose configuration', lambda: Deployment(root).compose('config', '--quiet'))
            finally:
                server.RELEASE = original
    else:
        print('WARN: no --release supplied; program payload has not been checked')
    print('Preflight: %d failure(s)' % len(failed))
    return not failed


def require(condition, message):
    if not condition:
        raise ValueError(message)


def prepare(root, port, bind):
    from server import configuration, initialize
    ownership(root, create=True)
    web_ownership(create=True)
    (WEB_ROOT / 'releases').mkdir(exist_ok=True)
    (WEB_ROOT / 'releases').chmod(0o755)
    WEB_ROOT.chmod(0o755)
    with locked(root):
        for name, mode in [('releases', 0o755), ('backups', 0o700)]:
            (root / name).mkdir(exist_ok=True)
            (root / name).chmod(mode)
        root.chmod(0o700)
        if (root / '.env').exists():
            (root / '.env').chmod(0o600)
            configuration(root)
        else:
            ${hash} Do not generate new credentials for a surviving old database.
            resources = inventory()
            require(not resources['volumes'] and not resources['containers'], 'Existing project resources with missing credentials: restore .env or explicitly uninstall first')
            initialize(root, port, bind)
    print('Prepared directories and credentials. No application service started.')


def protected_releases(root, resources):
    protected = set()
    for path in (root / 'current',):
        if path.is_symlink():
            protected.add(path.resolve())
    if (root / 'previous-release.txt').exists():
        protected.add(Path((root / 'previous-release.txt').read_text().strip()).resolve())
    if (root / 'active.json').exists():
        state = json.loads((root / 'active.json').read_text())
        protected.add((root / 'releases' / state['release']).resolve())
        protected.add((WEB_ROOT / 'releases' / state['release']).resolve())
    if (WEB_ROOT / 'current').is_symlink():
        protected.add((WEB_ROOT / 'current').resolve())
    for c in resources['containers']:
        working = c.get('Config', {}).get('Labels', {}).get('com.docker.compose.project.working_dir')
        if working:
            protected.add(Path(working).resolve())
        for mount in c.get('Mounts', []):
            if mount.get('Type') == 'bind':
                source = Path(mount['Source']).resolve()
                protected.update(p for p in (root / 'releases').iterdir() if p == source or p in source.parents)
    return protected


def prune(root, selected, execute, confirm):
    with locked(root):
        protected = protected_releases(root, inventory())
        targets = []
        for name in selected:
            require(re.fullmatch(r'[a-z0-9][a-z0-9-]{1,80}', name), 'Invalid release ID')
            path = root / 'releases' / name
            require(not path.is_symlink() and path.is_dir(), 'Not a release directory')
            require(path.resolve() not in protected, 'Release is active, pending or previous; cannot remove')
            from delivery import verify_release
            require(verify_release(path)['release_id'] == name, 'Invalid release identity')
            targets.append(path)
        print('Release cleanup plan: ' + ', '.join(map(str, targets)))
        if execute:
            require(confirm == PROJECT, 'Use --confirm ${artifactId}')
            for path in targets:
                shutil.rmtree(path)
                frontend = WEB_ROOT / 'releases' / path.name
                if frontend.exists() and not frontend.is_symlink():
                    shutil.rmtree(frontend)
        else:
            print('Preview only. Add --execute --confirm ${artifactId} to apply.')


def uninstall(root, data=False, code=False, backups=False, config=False, execute=False, confirm=None):
    with locked(root):
        resources = inventory()
        ${hash} Verify project ownership again from inspect, not a name prefix.
        for kind, entries in resources.items():
            for item in entries:
                labels = item.get('Config', {}).get('Labels', {}) if kind == 'containers' else item.get('Labels', {})
                require((labels or {}).get(LABEL) == PROJECT, 'Resource ownership mismatch')
        expected_containers = {c['Id'] for c in resources['containers']}
        for c in resources['containers']:
            working = c.get('Config', {}).get('Labels', {}).get('com.docker.compose.project.working_dir')
            require(working and Path(working).resolve().parent == root / 'releases',
                    'Container belongs to a different deployment root')
        for n in resources['networks']:
            require(set((n.get('Containers') or {}).keys()).issubset(expected_containers), 'Network has foreign containers')
        if data:
            all_ids = run('docker', 'ps', '-aq').split()
            all_containers = json.loads(run('docker', 'inspect', *all_ids)) if all_ids else []
            volumes = {v['Name'] for v in resources['volumes']}
            for c in all_containers:
                if c['Id'] not in expected_containers:
                    require(not any(m.get('Name') in volumes for m in c.get('Mounts', [])), 'Project volume used by foreign container')
        print('Uninstall plan:')
        for kind in ('containers', 'networks', 'volumes'):
            if kind != 'volumes' or data:
                print(kind + ': ' + ', '.join(i.get('Name', i.get('Id', '')) for i in resources[kind]))
        targets = []
        if code:
            targets += [root / 'releases', root / 'current', root / 'previous-release.txt', root / 'active.json']
        if backups:
            targets.append(root / 'backups')
        if config:
            require(data, 'Removing credentials requires --remove-data')
            targets.append(root / '.env')
        for path in targets:
            require(path.parent == root and (not path.is_symlink() or path.name == 'current'), 'Unsafe removal target')
            if path.is_dir():
                require(not any(p.is_mount() for p in [path, *path.rglob('*')] if not p.is_symlink()),
                        'Refusing to remove a mounted filesystem')
            print('path: ' + str(path))
        frontend_targets = [WEB_ROOT / 'releases', WEB_ROOT / 'current'] if code else []
        for path in frontend_targets:
            require(path.parent == WEB_ROOT and (not path.is_symlink() or path.name == 'current'), 'Unsafe frontend removal target')
            print('path: ' + str(path))
        if not execute:
            print('Preview only. Add --execute --confirm ${artifactId} to apply.')
            return
        require(confirm == PROJECT, 'Use --confirm ${artifactId}')
        for c in resources['containers']:
            run('docker', 'rm', '-f', c['Id'])
        for n in resources['networks']:
            run('docker', 'network', 'rm', n['Id'])
        if data:
            for v in resources['volumes']:
                run('docker', 'volume', 'rm', v['Name'])
        for path in targets:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        for path in frontend_targets:
            if path.is_symlink() or path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        print('Selected project resources removed. Shared images and unrelated projects retained.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'prepare', 'prune', 'uninstall'])
    parser.add_argument('--root', default='/opt/${artifactId}')
    parser.add_argument('--release', type=Path)
    parser.add_argument('--mode', choices=['first', 'update'], default='first')
    parser.add_argument('--port', type=int, default=${httpPort})
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--fix', action='store_true')
    parser.add_argument('--release-id', action='append', default=[])
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm')
    for name in ('data', 'code', 'backups', 'config'):
        parser.add_argument('--remove-' + name, action='store_true')
    args = parser.parse_args()
    require(sys.platform == 'linux', 'Run on the Linux server')
    root = root_path(args.root)
    require(1 <= args.port <= 65535, 'Port must be 1-65535')
    if args.action == 'preflight':
        sys.exit(0 if preflight(root, args.release, args.port, args.mode) else 1)
    elif args.action == 'prepare':
        if args.fix:
            prepare(root, args.port, args.bind)
        else:
            print('Preview: create releases/backups and missing .env, repair permissions. Add --fix to apply.')
    elif args.action == 'prune':
        require(args.release_id, 'Specify at least one --release-id')
        prune(root, args.release_id, args.execute, args.confirm)
    else:
        uninstall(root, args.remove_data, args.remove_code, args.remove_backups, args.remove_config, args.execute, args.confirm)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('Host operation failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
