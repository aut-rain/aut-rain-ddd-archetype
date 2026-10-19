#set( $dollar = '$' )
#set( $hash = '#' )
"""Shared release checks. Standard library only; no services are started."""
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

${hash} Release path -> source path relative to the project root. Only this allowlist is
${hash} copied, so local credentials and dev-only configuration never enter a release.
DEPLOY_FILES = {
    'environment/docker-compose.yml': 'docs/dev-ops/environment/docker-compose.yml',
    'environment/mysql/compose.yaml': 'docs/dev-ops/environment/mysql/compose.yaml',
    'environment/mysql/conf.d/my.cnf': 'docs/dev-ops/environment/mysql/conf.d/my.cnf',
    'environment/mysql/initdb/10-middleware.sh': 'docs/dev-ops/environment/mysql/initdb/10-middleware.sh',
    'environment/sql/nacos.sql': 'docs/dev-ops/environment/sql/nacos.sql',
    'environment/sql/xxl-job.sql': 'docs/dev-ops/environment/sql/xxl-job.sql',
    'environment/redis/redis.conf': 'docs/dev-ops/environment/redis/redis.conf',
    'environment/rocketmq/broker.conf': 'docs/dev-ops/environment/rocketmq/broker.conf',
    'app/docker-compose.yml': 'docs/dev-ops/app/docker-compose.yml',
    'app/Dockerfile': 'app-backend/${artifactId}-app/Dockerfile',
    'environment/nginx/Dockerfile': 'docs/dev-ops/environment/nginx/Dockerfile',
    'environment/nginx/conf.d/default.conf': 'docs/dev-ops/environment/nginx/conf.d/default.conf',
    '.dockerignore': 'docs/dev-ops/.dockerignore',
    'preflight/server-preflight.sh': 'docs/dev-script/deployment/preflight/server-preflight.sh',
    'prepare/prepare-server.sh': 'docs/dev-script/deployment/prepare/prepare-server.sh',
    'prepare/prune-releases.sh': 'docs/dev-script/deployment/prepare/prune-releases.sh',
    'prepare/install-dependencies.sh': 'docs/dev-script/deployment/prepare/install-dependencies.sh',
    'deploy/first-deploy.sh': 'docs/dev-script/deployment/deploy/first-deploy.sh',
    'deploy/deploy-server.sh': 'docs/dev-script/deployment/deploy/deploy-server.sh',
    'deploy/iteration/frontend.sh': 'docs/dev-script/deployment/deploy/iteration/frontend.sh',
    'deploy/iteration/backend.sh': 'docs/dev-script/deployment/deploy/iteration/backend.sh',
    'deploy/iteration/full.sh': 'docs/dev-script/deployment/deploy/iteration/full.sh',
    'health/health-check.sh': 'docs/dev-script/deployment/health/health-check.sh',
    'health/monitor.sh': 'docs/dev-script/deployment/health/monitor.sh',
    'uninstall/uninstall.sh': 'docs/dev-script/deployment/uninstall/uninstall.sh',
    'lib/server.py': 'docs/dev-script/deployment/lib/server.py',
    'lib/host.py': 'docs/dev-script/deployment/lib/host.py',
    'lib/delivery.py': 'docs/dev-script/deployment/lib/delivery.py',
    'lib/bootstrap_server.py': 'docs/dev-script/deployment/lib/bootstrap_server.py',
    '.env.example': 'docs/dev-script/deployment/prepare/.env.example',
    'README.md': 'docs/dev-script/deployment/README.md',
}



def deployment_sources(root):
    """Resolve the release allowlist against the generated project root."""
    root = Path(root).resolve()
    sources = {}
    for destination, name in DEPLOY_FILES.items():
        relative_file(name)
        path = root / name
        if not path.is_file():
            raise ValueError('Missing deployment source: ' + name)
        if root not in path.resolve().parents:
            raise ValueError('Deployment source is outside project: ' + name)
        sources[destination] = path
    return sources


def validate_iteration(previous, current, mode):
    """Use the same component boundary at packaging time and on the server."""
    if mode == 'full':
        return
    if mode not in ('frontend', 'backend'):
        raise ValueError('Invalid iteration component: ' + mode)
    def protected(files):
        return {n: h for n, h in files.items()
                if n in ('app/docker-compose.yml', '.dockerignore')
                or (n.startswith('environment/') and not n.startswith('environment/nginx/'))
                or (mode == 'frontend' and n in ('app.jar', 'app/Dockerfile'))
                or (mode == 'backend' and (n.startswith('web/') or n.startswith('environment/nginx/')))}
    if protected(previous['files']) != protected(current['files']):
        raise ValueError('Unselected component/infrastructure changed; rebuild with the current base package or use full')
    if mode == 'frontend' and previous['migrations'] != current['migrations']:
        raise ValueError('Frontend iteration cannot change migrations')


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def relative_file(name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ('..', '.') for p in path.parts) or '\\' in name or ':' in name:
        raise ValueError('Unsafe release path: ' + name)
    return path


def check_payload(directory, migrations):
    directory = Path(directory)
    if not migrations:
        raise ValueError('Migration list is empty')
    with zipfile.ZipFile(directory / 'app.jar') as jar:
        if 'BOOT-INF/classes/application-prod.yml' not in jar.namelist():
            raise ValueError('Not a Spring Boot production JAR')
        actual = {Path(n).name for n in jar.namelist()
                  if n.startswith('BOOT-INF/classes/db/migration/V') and n.endswith('.sql')}
        if actual != set(migrations):
            raise ValueError('JAR migration set differs from release manifest/source')
        for name, checksum in migrations.items():
            data = jar.read('BOOT-INF/classes/db/migration/' + name)
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError('Migration checksum differs: ' + name)
    index = (directory / 'web/index.html').read_text(encoding='utf-8')
    assets = re.findall(r'(?:src|href)=["\'](/assets/[^"\']+)["\']', index)
    if not assets or not any(a.endswith('.js') for a in assets):
        raise ValueError('Built frontend index has no JavaScript assets')
    for asset in assets:
        relative_file(asset.lstrip('/'))
        if not (directory / 'web' / asset.lstrip('/')).is_file():
            raise ValueError('Missing frontend asset: ' + asset)
    for path in (directory / 'web').rglob('*'):
        if path.is_file() and path.suffix in ('.html', '.js', '.css'):
            if re.search(r'(?:localhost|127\.0\.0\.1):(?:5137|8080)', path.read_text(encoding='utf-8')):
                raise ValueError('Development address embedded in ' + str(path))


def verify_release(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'release.json').read_text(encoding='utf-8'))
    if manifest.get('application') != '${artifactId}' or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,80}', manifest.get('release_id', '')):
        raise ValueError('Invalid release identity')
    files = manifest['files']
    required = set(DEPLOY_FILES) | {'app.jar', 'web/index.html'}
    if not required.issubset(files):
        raise ValueError('Release is missing required deployment files')
    for name, checksum in files.items():
        relative_file(name)
        path = directory / name
        if path.is_symlink() or not path.is_file() or directory not in path.resolve().parents:
            raise ValueError('Invalid file: ' + name)
        if digest(path) != checksum:
            raise ValueError('Release checksum mismatch: ' + name)
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    ${hash} Python writes its own bytecode; all other unexpected payloads are rejected.
    actual = {n for n in actual if '__pycache__' not in PurePosixPath(n).parts}
    if actual != set(files) | {'release.json'}:
        raise ValueError('Unexpected files in release directory')
    check_payload(directory, manifest['migrations'])
    return manifest
