#set( $dollar = '$' )
#set( $hash = '#' )
"""Native Windows/Linux build and SSH delivery; never starts the application."""
import argparse
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LIB = HERE.parent / 'lib'
sys.path.insert(0, str(LIB))
from delivery import deployment_sources, validate_iteration, check_payload, digest, relative_file, verify_release


def tool(name):
    found = shutil.which(name + '.cmd') if os.name == 'nt' else None
    found = found or shutil.which(name)
    if not found:
        raise RuntimeError('Missing command: ' + name)
    return found


def run(args, cwd=ROOT, capture=False):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def build(component='full'):
    deployment_sources(ROOT)
    if component != 'backend':
        node, corepack = tool('node'), tool('corepack')
        if run([node, '--version'], capture=True).strip() != 'v22.22.0':
            raise RuntimeError('Build requires Node.js 22.22.0')
        expected = json.loads((ROOT / 'web/package.json').read_text())['packageManager'].split('@')[1]
        if run([corepack, 'pnpm', '--version'], cwd=ROOT / 'web', capture=True).strip() != expected:
            raise RuntimeError('Corepack did not select the package.json pnpm version')
    if component != 'frontend':
        mvn = tool('mvn')
        print('==> Backend package and tests without listening ports', flush=True)
        run([mvn, '-B', '-ntp', '-f', 'app-backend/pom.xml', 'clean', 'package',
             '-DskipTests=false'])
    if component != 'backend':
        print('==> Frontend install, checks and build', flush=True)
        run([corepack, 'pnpm', 'install', '--frozen-lockfile'], cwd=ROOT / 'web')
        for task in ('typecheck', 'lint', 'test', 'build'):
            run([corepack, 'pnpm', task], cwd=ROOT / 'web')


def release_permissions(member):
    ${hash} Windows staging files may otherwise be archived as world-writable, which
    ${hash} causes MySQL to ignore mounted .cnf files on the Linux server.
    member.mode = 0o755 if member.isdir() else 0o644
    return member


def pack(component='full', base_package=None):
    sources = deployment_sources(ROOT)
    output = ROOT / '.runtime/delivery'
    output.mkdir(parents=True, exist_ok=True)
    release = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ').lower() + '-' + uuid.uuid4().hex[:8]
    migrations = {p.name: digest(p) for p in sorted((ROOT / 'app-backend/${artifactId}-app/src/main/resources/db/migration').glob('V*.sql'))}
    with tempfile.TemporaryDirectory(prefix='stage-', dir=output) as temp:
        stage = Path(temp) / release
        stage.mkdir()
        base = None
        if component != 'full':
            if base_package is None:
                raise ValueError('Partial packages require --base-package from the last successful deployment')
            base_id = verify_archive(base_package)
            with tarfile.open(base_package, 'r:gz') as archive:
                archive.extractall(Path(temp) / 'base', filter='data')
            base = Path(temp) / 'base' / base_id
            if component == 'frontend':
                migrations = verify_release(base)['migrations']
        shutil.copy2(base / 'app.jar' if component == 'frontend' else ROOT / 'app-backend/${artifactId}-app/target/${artifactId}-app.jar', stage / 'app.jar')
        shutil.copytree(base / 'web' if component == 'backend' else ROOT / 'web/dist', stage / 'web')
        for name, source in sources.items():
            ${hash} Deployment text must use LF even on Windows checkouts.
            destination = stage / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(source.read_text(encoding='utf-8-sig'), encoding='utf-8', newline='\n')
        check_payload(stage, migrations)
        revision, dirty = 'unversioned', True
        if (ROOT / '.git').exists():
            revision = run([tool('git'), 'rev-parse', 'HEAD'], capture=True).strip()
            dirty = bool(run([tool('git'), 'status', '--porcelain'], capture=True).strip())
        manifest = {'application': '${artifactId}', 'release_id': release,
                    'component': component,
                    'git_revision': revision, 'working_tree_dirty': dirty,
                    'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'migrations': migrations,
                    'files': {p.relative_to(stage).as_posix(): digest(p) for p in sorted(stage.rglob('*')) if p.is_file()}}
        if base is not None:
            validate_iteration(verify_release(base), manifest, component)
        (stage / 'release.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        verify_release(stage)
        package = output / (release + '.tar.gz')
        with tarfile.open(package, 'w:gz') as archive:
            archive.add(stage, arcname=release, filter=release_permissions)
    package.with_name(package.name + '.sha256').write_text(digest(package) + '  ' + package.name + '\n', encoding='ascii', newline='\n')
    return package


def verify_archive(package):
    expected = package.with_name(package.name + '.sha256').read_text(encoding='ascii').split()[0]
    if digest(package) != expected:
        raise ValueError('Archive checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='release-verify-') as temp:
        with tarfile.open(package, 'r:gz') as archive:
            members = archive.getmembers()
            roots = set()
            for member in members:
                path = relative_file(member.name)
                roots.add(path.parts[0])
                if not (member.isfile() or member.isdir()):
                    raise ValueError('Archive contains a link or special file')
            if len(roots) != 1:
                raise ValueError('Archive must have one release root')
            archive.extractall(temp, members=members)
        stage = Path(temp) / roots.pop()
        manifest = verify_release(stage)
        if stage.name != manifest['release_id'] or package.name != stage.name + '.tar.gz':
            raise ValueError('Archive name differs from release ID')
        return manifest['release_id']


def toolkit():
    output = ROOT / '.runtime/delivery'
    output.mkdir(parents=True, exist_ok=True)
    package = output / 'deployment-tools.tar.gz'
    with tarfile.open(package, 'w:gz') as archive:
        for path in sorted(HERE.parent.rglob('*')):
            if path.is_file() and not path.is_symlink() and (path.suffix in ('.py', '.sh', '.ps1', '.md') or path.name == '.env.example'):
                archive.add(path, arcname='deployment-tools/' + path.relative_to(HERE.parent).as_posix(), filter=release_permissions)
    Path(str(package) + '.sha256').write_text(digest(package) + '  ' + package.name + '\n', encoding='ascii', newline='\n')
    return package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', help='Explicit user@host or SSH config alias')
    parser.add_argument('--ssh-port', type=int, default=22)
    parser.add_argument('--remote-dir', default='${artifactId}-incoming')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--build-only', action='store_true')
    modes.add_argument('--upload-only', action='store_true')
    modes.add_argument('--tools-only', action='store_true', help='Upload management scripts without building the application')
    parser.add_argument('--package', type=Path, help='Existing archive, required with --upload-only')
    parser.add_argument('--component', choices=['full', 'frontend', 'backend'], default='full')
    parser.add_argument('--base-package', type=Path, help='Last successful package, required for partial builds')
    args = parser.parse_args()
    if not args.build_only and not args.server:
        parser.error('Provide --server or --build-only; no server is selected implicitly')
    if args.upload_only != bool(args.package):
        parser.error('--upload-only and --package must be used together')
    if (args.tools_only or args.upload_only) and (args.component != 'full' or args.base_package):
        parser.error('Component/base options apply to new application builds only')
    if not args.upload_only and (args.component != 'full') != bool(args.base_package):
        parser.error('Partial builds require --base-package; full builds do not use a base')
    if args.server and not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.@-]*', args.server):
        parser.error('Invalid server; use user@host or an SSH alias')
    if not 1 <= args.ssh_port <= 65535:
        parser.error('Invalid SSH port')
    if not re.fullmatch(r'/?[A-Za-z0-9_-][A-Za-z0-9_./-]*', args.remote_dir) or '..' in args.remote_dir.split('/'):
        parser.error('Remote path must use letters, digits, /, _, -, . without parent traversal')
    if args.upload_only:
        package = args.package.resolve()
    elif args.tools_only:
        package = toolkit()
    else:
        if args.base_package:
            verify_archive(args.base_package)
        build(args.component)
        package = pack(args.component, args.base_package)
    release = 'deployment-tools' if args.tools_only else verify_archive(package)
    print('Verified package: ' + str(package), flush=True)
    if args.build_only:
        return
    ${hash} No ControlMaster on Windows; native OpenSSH, no WSL and no password storage.
    options = ['-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'ServerAliveInterval=15']
    run([tool('ssh'), *options, '-p', str(args.ssh_port), args.server,
         'mkdir -p -- ' + shlex.quote(args.remote_dir)])
    run([tool('scp'), *options, '-P', str(args.ssh_port), str(package),
         str(package) + '.sha256', str(LIB / 'bootstrap_server.py'), str(LIB / 'delivery.py'),
         args.server + ':' + args.remote_dir + '/'])
    print('Uploaded ' + release + '. No remote application was started.')
    print('On the server, run bootstrap_server.py extract; follow README.md for init and deploy.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print('Delivery failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
