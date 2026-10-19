#set( $dollar = '$' )
#set( $hash = '#' )
"""Linux host operations for the isolated ${artifactId} Compose project."""
import argparse
import base64
import datetime
import gzip
import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delivery import verify_release, validate_iteration

RELEASE = Path(__file__).resolve().parent.parent
PROJECT = '${artifactId}'
WEB_ROOT = Path('/var/www/${artifactId}')
SECRET_KEYS = ('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'REDIS_PASSWORD',
               'NACOS_DB_PASSWORD', 'NACOS_AUTH_IDENTITY_VALUE',
               'XXL_JOB_DB_PASSWORD', 'XXL_JOB_ACCESS_TOKEN', 'XXL_JOB_ADMIN_PASSWORD')
KEYS = {'HTTP_BIND', 'HTTP_PORT', 'NACOS_AUTH_TOKEN', *SECRET_KEYS}
INFRASTRUCTURE = ('mysql', 'redis', 'nacos', 'rocketmq-namesrv', 'rocketmq-broker', 'xxl-job-admin')


def initialize(root, port, bind):
    ipaddress.IPv4Address(bind)
    if not 1 <= port <= 65535:
        raise ValueError('Invalid HTTP port')
    root.mkdir(parents=True, exist_ok=True)
    WEB_ROOT.mkdir(parents=True, exist_ok=True)
    marker = WEB_ROOT / '.${artifactId}-managed'
    if marker.exists() and marker.read_text().strip() != PROJECT:
        raise ValueError('Invalid frontend managed-directory marker')
    if not marker.exists() and any(path.name not in {'.${artifactId}-managed', 'releases', 'current'} for path in WEB_ROOT.iterdir()):
        raise ValueError('Unknown frontend contents: refusing to adopt this root')
    marker.write_text(PROJECT + '\n')
    (WEB_ROOT / 'releases').mkdir(exist_ok=True)
    ${hash} Exclusive creation: never overwrite credentials of an existing database.
    fd = os.open(root / '.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write('HTTP_BIND=' + bind + '\nHTTP_PORT=' + str(port) + '\n')
        for key in SECRET_KEYS:
            stream.write(key + '=' + secrets.token_hex(32) + '\n')
        stream.write('NACOS_AUTH_TOKEN=' + base64.b64encode(secrets.token_bytes(48)).decode('ascii') + '\n')
    print('Created server-only credentials: ' + str(root / '.env'))


def configuration(root):
    path = root / '.env'
    if path.is_symlink():
        raise ValueError('.env cannot be a symlink')
    if path.stat().st_mode & 0o077:
        raise ValueError('Run chmod 600 on ' + str(path))
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('${hash}'):
            continue
        key, sep, value = line.partition('=')
        if not sep or key not in KEYS or key in values:
            raise ValueError('Unknown/duplicate configuration key; use plain KEY=value')
        values[key] = value
    if set(values) != KEYS:
        raise ValueError('Configuration is incomplete; see .env.example')
    for key in SECRET_KEYS:
        if not re.fullmatch(r'[A-Za-z0-9_-]{24,128}', values[key]):
            raise ValueError(key + ' must contain 24-128 letters/digits/_/-; run init to generate it')
    if len({values[key] for key in SECRET_KEYS}) != len(SECRET_KEYS):
        raise ValueError('Use different component passwords/tokens')
    try:
        token = base64.b64decode(values['NACOS_AUTH_TOKEN'], validate=True)
    except ValueError:
        raise ValueError('NACOS_AUTH_TOKEN must be valid Base64') from None
    if len(token) < 32:
        raise ValueError('NACOS_AUTH_TOKEN must encode at least 32 bytes')
    ipaddress.IPv4Address(values['HTTP_BIND'])
    if not values['HTTP_PORT'].isdigit() or not 1 <= int(values['HTTP_PORT']) <= 65535:
        raise ValueError('Invalid HTTP_PORT')
    return values


class Deployment:
    def __init__(self, root):
        self.root = root
        self.manifest = verify_release(RELEASE)
        if RELEASE.parent != root / 'releases' or RELEASE.name != self.manifest['release_id']:
            raise ValueError('Extract the release into ' + str(root / 'releases/<release-id>'))
        self.config = configuration(root)
        self.web_release = WEB_ROOT / 'releases' / self.manifest['release_id']
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('COMPOSE_')
                    and k not in ('APP_RELEASE_ID', 'WEB_RELEASE_ID')}
        self.env.update(self.config)
        self.env['RELEASE_ID'] = self.manifest['release_id']
        self.env['WEB_ROOT'] = str(self.web_release)
        state_file = root / 'active.json'
        self.state = json.loads(state_file.read_text()) if state_file.exists() else None
        if self.state:
            for component, variable in (('app', 'APP_RELEASE_ID'), ('web', 'WEB_RELEASE_ID')):
                tag = self.state[component]
                if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,80}', tag):
                    raise ValueError('Invalid active component version')
                self.env[variable] = tag
        self.prefix = ['docker', 'compose', '-p', PROJECT, '--project-directory', str(RELEASE / 'environment'),
                       '--env-file', str(root / '.env'),
                       '-f', str(RELEASE / 'environment/docker-compose.yml'),
                       '-f', str(RELEASE / 'app/docker-compose.yml')]

    def compose(self, *args, capture=False):
        return subprocess.run(self.prefix + list(args), env=self.env, cwd=RELEASE,
                              check=True, text=True, stdout=subprocess.PIPE if capture else None).stdout

    def sql(self, query):
        return self.compose('exec', '-T', 'mysql', 'sh', '-c',
                            'MYSQL_PWD="${dollar}MYSQL_PASSWORD" exec mysql -u ${databaseName} -D ${databaseName} -N -B -e "${dollar}1"',
                            'query', query, capture=True).strip()

    def backup(self):
        folder = self.root / 'backups'
        folder.mkdir(mode=0o700, exist_ok=True)
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        path = folder / (stamp + '-' + secrets.token_hex(3) + '.sql.gz')
        ${hash} Back up the application schema only, including Flyway and the runtime catalog.
        args = self.prefix + ['exec', '-T', 'mysql', 'sh', '-c',
                             'MYSQL_PWD="${dollar}MYSQL_PASSWORD" exec mysqldump -u ${databaseName} '
                             '--single-transaction --quick --no-tablespaces --set-gtid-purged=OFF '
                             '--skip-lock-tables --databases ${databaseName}']
        with path.open('xb') as raw:
            os.chmod(path, 0o600)
            with gzip.GzipFile(fileobj=raw, mode='wb') as compressed:
                with subprocess.Popen(args, env=self.env, stdout=subprocess.PIPE) as process:
                    shutil.copyfileobj(process.stdout, compressed)
                    if process.wait() != 0:
                        raise RuntimeError('Backup failed; incomplete backup retained at ' + str(path))
        print('Database backup: ' + str(path), flush=True)
        return path

    def request(self, path):
        host = self.config['HTTP_BIND']
        if host == '0.0.0.0':
            host = '127.0.0.1'
        url = 'http://' + host + ':' + self.config['HTTP_PORT'] + path
        ${hash} Local validation must not go through an inherited HTTP proxy.
        for attempt in range(5):
            try:
                with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=10) as response:
                    return response.read(), response.headers.get_content_type()
            except urllib.error.URLError:
                if attempt == 4:
                    raise
                time.sleep(1)

    def verify(self):
        if self.state and self.state.get('release') != self.manifest['release_id']:
            raise ValueError('Run health checks from the active release directory')
        if self.state and self.state.get('status') != 'healthy':
            raise ValueError('Incomplete deployment recorded; inspect the pending release and use full iteration to recover')
        self.verify_runtime()
        self.verify_infrastructure()
        health, _ = self.request('/healthz')
        if json.loads(health).get('status') != 'UP':
            raise ValueError('Readiness is not UP')
        bootstrap, mime = self.request('/api/v1/ping')
        body = json.loads(bootstrap)
        if mime != 'application/json' or body.get('code') != '0':
            raise ValueError('Ping or API proxy check failed')
        index, mime = self.request('/')
        if mime != 'text/html' or index != (RELEASE / 'web/index.html').read_bytes():
            raise ValueError('Served frontend differs from this release')
        for route in ('/welcome',):
            html, mime = self.request(route)
            if mime != 'text/html' or html != index:
                raise ValueError('SPA route fallback failed: ' + route)
        for asset in re.findall(r'(?:src|href)=["\'](/assets/[^"\']+)["\']', index.decode()):
            data, mime = self.request(asset)
            if data != (RELEASE / 'web' / asset.lstrip('/')).read_bytes() or mime == 'text/html':
                raise ValueError('Static asset check failed: ' + asset)
        rows = self.sql('SELECT script FROM flyway_schema_history WHERE success=1 AND version IS NOT NULL')
        if set(rows.splitlines()) != set(self.manifest['migrations']):
            raise ValueError('Applied migrations differ from this release')
        if self.sql('SELECT COUNT(*) FROM flyway_schema_history WHERE success=0') != '0':
            raise ValueError('Flyway has failed migrations')
        if self.sql('SELECT COUNT(*) FROM information_schema.referential_constraints WHERE constraint_schema=DATABASE()') != '0':
            raise ValueError('Physical foreign keys detected')
        print('Verified readiness, API, SPA routes, assets, Flyway and zero physical foreign keys.')

    def deploy(self):
        self.validate_mode('full')
        self.env['APP_RELEASE_ID'] = self.manifest['release_id']
        self.env['WEB_RELEASE_ID'] = self.manifest['release_id']
        self.publish_frontend()
        ${hash} Reject altered bundles and bad config before changing running containers.
        self.compose('config', '--quiet')
        self.compose('build', '--pull', 'app', 'nginx')
        self.record_attempt('full')
        self.compose('up', '-d', '--wait', '--wait-timeout', '360', *INFRASTRUCTURE)
        print('==> Maintenance window: stopping project frontend and backend', flush=True)
        self.compose('stop', 'nginx', 'app')
        if self.sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()") != '0':
            self.backup()
        ${hash} MySQL stays running. Flyway migrations execute in the new prod application.
        self.compose('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '360', 'app')
        self.compose('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '120', 'nginx')
        self.verify()
        self.commit_release()

    def commit_release(self):
        current = self.root / 'current'
        if current.exists() and not current.is_symlink():
            raise ValueError('current must be a symlink, refusing to overwrite')
        if current.is_symlink():
            (self.root / 'previous-release.txt').write_text(str(current.resolve()) + '\n')
        temporary = self.root / ('current-' + secrets.token_hex(4))
        temporary.symlink_to(RELEASE, target_is_directory=True)
        temporary.replace(current)
        self.commit_frontend()
        self.write_state({'app': self.env['APP_RELEASE_ID'], 'web': self.env['WEB_RELEASE_ID'],
                          'release': self.manifest['release_id'], 'status': 'healthy'})
        print('Deployed: ' + self.manifest['release_id'])

    def write_state(self, state):
        temporary = self.root / 'active.json.tmp'
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(self.root / 'active.json')

    def record_attempt(self, mode):
        self.state = None
        self.write_state({'app': self.env['APP_RELEASE_ID'], 'web': self.env['WEB_RELEASE_ID'],
                          'release': self.manifest['release_id'], 'status': 'deploying', 'mode': mode})

    def validate_mode(self, mode):
        current = self.root / 'current'
        if current.exists() and not current.is_symlink():
            raise ValueError('current must be a symlink')
        if mode == 'full':
            return
        if not current.is_symlink() or not self.state or self.state.get('status') != 'healthy':
            raise ValueError('Partial iteration requires a healthy successful full deployment; use full to recover')
        previous_dir = current.resolve()
        if previous_dir.parent != self.root / 'releases':
            raise ValueError('Current release is outside managed releases')
        previous = verify_release(previous_dir)
        if self.state.get('release') != previous['release_id']:
            raise ValueError('Active state and current release disagree')
        validate_iteration(previous, self.manifest, mode)
        self.env['WEB_ROOT'] = str(WEB_ROOT / 'releases' / previous['release_id'])
        self.verify_runtime()

    def publish_frontend(self):
        WEB_ROOT.mkdir(parents=True, exist_ok=True)
        marker = WEB_ROOT / '.${artifactId}-managed'
        if marker.exists() and marker.read_text().strip() != PROJECT:
            raise ValueError('Invalid frontend directory marker')
        marker.write_text(PROJECT + '\n')
        releases = WEB_ROOT / 'releases'
        releases.mkdir(exist_ok=True)
        if (releases / self.manifest['release_id']).is_symlink():
            raise ValueError('Frontend release directory cannot be a symlink')
        temporary = releases / ('.' + self.manifest['release_id'] + '.tmp-' + secrets.token_hex(4))
        shutil.copytree(RELEASE / 'web', temporary)
        destination = releases / self.manifest['release_id']
        if destination.exists():
            if destination.is_symlink():
                raise ValueError('Frontend release directory cannot be a symlink')
            shutil.rmtree(destination)
        temporary.replace(destination)
        self.web_release = destination
        self.env['WEB_ROOT'] = str(destination)

    def commit_frontend(self):
        current = WEB_ROOT / 'current'
        if current.exists() and not current.is_symlink():
            raise ValueError('frontend current must be a symlink')
        temporary = WEB_ROOT / ('current-' + secrets.token_hex(4))
        temporary.symlink_to(self.web_release, target_is_directory=True)
        temporary.replace(current)

    def verify_infrastructure(self):
        for service in INFRASTRUCTURE:
            ids = self.compose('ps', '-a', '-q', service, capture=True).split()
            if len(ids) != 1:
                raise ValueError('Expected one infrastructure container for ' + service)
            container = json.loads(subprocess.check_output(['docker', 'inspect', ids[0]], text=True))[0]
            if container['State'].get('Health', {}).get('Status') != 'healthy':
                raise ValueError('Infrastructure is unhealthy: ' + service)

    def verify_runtime(self):
        for service, tag in (('app', self.env.get('APP_RELEASE_ID')), ('nginx', self.env.get('WEB_RELEASE_ID'))):
            ids = self.compose('ps', '-a', '-q', service, capture=True).split()
            if len(ids) != 1:
                raise ValueError('Expected one container for ' + service)
            container = json.loads(subprocess.check_output(['docker', 'inspect', ids[0]], text=True))[0]
            image = '${artifactId}/' + ('app' if service == 'app' else 'web') + ':' + str(tag)
            if container['Config']['Image'] != image or container['State'].get('Health', {}).get('Status') != 'healthy':
                raise ValueError('Active image or container health differs: ' + service)

    def deploy_frontend(self):
        self.validate_mode('frontend')
        self.env['WEB_RELEASE_ID'] = self.manifest['release_id']
        self.publish_frontend()
        self.compose('config', '--quiet')
        self.compose('build', '--pull', 'nginx')
        self.record_attempt('frontend')
        self.compose('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '120', 'nginx')
        self.verify()
        self.commit_release()

    def deploy_backend(self):
        self.validate_mode('backend')
        self.env['APP_RELEASE_ID'] = self.manifest['release_id']
        self.publish_frontend()
        self.compose('config', '--quiet')
        self.compose('build', '--pull', 'app')
        self.record_attempt('backend')
        self.compose('stop', 'app')
        if self.sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE()") != '0':
            self.backup()
        self.compose('up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '360', 'app')
        ${hash} Nginx resolves the upstream at configuration load; the new app may have
        ${hash} a different address. Reload without recreating the frontend container.
        self.compose('exec', '-T', 'nginx', 'nginx', '-s', 'reload')
        self.verify()
        self.commit_release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'check', 'deploy-first', 'deploy', 'deploy-full', 'deploy-frontend',
                                           'deploy-backend', 'verify', 'backup', 'status', 'logs', 'stop'])
    parser.add_argument('--root', type=Path, default=Path('/opt/${artifactId}'))
    parser.add_argument('--port', type=int, default=${httpPort}, help='Used only by init')
    parser.add_argument('--bind', default='0.0.0.0', help='Used only by init')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Run server operations on the Linux server; no WSL invocation is required locally')
    from host import root_path, ownership
    root = root_path(args.root)
    if args.action == 'init':
        from host import prepare
        prepare(root, args.port, args.bind)
        return
    ownership(root)
    ${hash} Serialize deployment, backup and maintenance operations for this environment.
    import fcntl
    with (root / '.deployment.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        deployment = Deployment(root)
        if args.action == 'deploy-first':
            from host import inventory
            resources = inventory()
            if deployment.state or (root / 'current').exists() or resources['containers'] or resources['volumes']:
                raise ValueError('First deployment refuses existing state/containers/volumes; inspect and explicitly clean or use iteration')
        if args.action.startswith('deploy'):
            from host import preflight
            if not preflight(root, RELEASE, int(deployment.config['HTTP_PORT']),
                             'first' if args.action == 'deploy-first' else 'update'):
                raise ValueError('Preflight failed; use preparation scripts and rerun')
        if args.action == 'check':
            deployment.compose('config', '--quiet')
            print('Release and Compose configuration passed. No services started.')
        elif args.action in ('deploy', 'deploy-full', 'deploy-first'):
            deployment.deploy()
        elif args.action == 'deploy-frontend':
            deployment.deploy_frontend()
        elif args.action == 'deploy-backend':
            deployment.deploy_backend()
        elif args.action == 'verify':
            deployment.verify()
        elif args.action == 'backup':
            deployment.backup()
        elif args.action == 'status':
            deployment.compose('ps', '-a')
        elif args.action == 'logs':
            deployment.compose('logs', '--tail', '200', 'app', 'nginx', *INFRASTRUCTURE)
        elif args.action == 'stop':
            deployment.compose('stop')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError, urllib.error.URLError) as error:
        print('Operation failed: ' + str(error), file=sys.stderr)
        print('No volumes were deleted and no automatic schema rollback was attempted. '
              'For deploy failures, inspect logs from this release before retrying.', file=sys.stderr)
        sys.exit(1)
