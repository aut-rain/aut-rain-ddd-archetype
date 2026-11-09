"""Generate and validate a project without starting any services. Requires Python 3.12+."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, cwd):
    print('> ' + ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, check=True)


def tool(name):
    value = shutil.which(name + '.cmd') if os.name == 'nt' else None
    value = value or shutil.which(name)
    if not value:
        raise RuntimeError('Missing command: ' + name)
    return value


def inspect(project, artifact, database, port, group_id='com.autrain', root_package=None):
    package = root_package or group_id.replace('-', '_') + '.' + artifact.replace('-', '_')
    java_path = 'src/main/java/' + package.replace('.', '/')
    expected = ['app-backend/pom.xml', '.gitignore', '.editorconfig', '.env.example', '.gitattributes',
                'README.md', 'web/package.json', 'web/pnpm-lock.yaml', 'docs/dev-ops/environment/docker-compose.yml',
                'docs/dev-ops/app/sh/build.sh', 'docs/dev-ops/app/sh/start.sh', 'docs/dev-ops/app/sh/stop.sh',
                'docs/dev-ops/app/psw/build.ps1', 'docs/dev-ops/app/psw/start.ps1', 'docs/dev-ops/app/psw/stop.ps1',
                'docs/dev-ops/app/.env.example']
    for name in expected:
        assert (project / name).is_file(), name
    assert not (project / 'docs/dev-script/deployment').exists()
    assert not (project / 'pom.xml').exists(), 'Backend reactor must remain under app-backend/'
    assert (project / 'app-backend' / (artifact + '-app') / 'Dockerfile').is_file()
    assert not (project / 'docs/dev-ops/app/Dockerfile').exists()
    for module in ('types', 'api', 'domain', 'infrastructure', 'trigger', 'app'):
        assert (project / 'app-backend' / (artifact + '-' + module) / 'pom.xml').is_file()
    assert (project / 'app-backend' / (artifact + '-types') / java_path / 'types/model/ApiResponse.java').is_file()
    assert (project / 'app-backend' / (artifact + '-types') / java_path / 'types/exception/BusinessException.java').is_file()
    expected_packages = {
        'api': ('api', 'api/model'),
        'app': ('config',),
        'domain': tuple('domain/' + domain + '/' + part
                        for domain in ('xxx', 'yyy')
                        for part in ('model/aggregate', 'model/entity', 'model/valobj', 'service', 'repository', 'adapter')),
        'infrastructure': ('infrastructure/persistent/dao', 'infrastructure/persistent/po',
                           'infrastructure/persistent/repository', 'infrastructure/gateway/api',
                           'infrastructure/gateway/dto', 'infrastructure/gateway/adapter', 'infrastructure/redis'),
        'trigger': ('trigger/http', 'trigger/rpc', 'trigger/listener', 'trigger/job'),
        'types': ('types/common',),
    }
    for module, packages in expected_packages.items():
        for name in packages:
            assert (project / 'app-backend' / (artifact + '-' + module) / java_path / name / 'package-info.java').is_file(), name
    trigger_root = project / 'app-backend' / (artifact + '-trigger') / java_path
    assert (trigger_root / 'trigger/http/HealthController.java').is_file()
    assert (trigger_root / 'trigger/http/ApiExceptionHandler.java').is_file()
    assert not (trigger_root / 'trigger/HealthController.java').exists()
    test_root = project / 'app-backend' / (artifact + '-app') / 'src/test/java' / package.replace('.', '/')
    assert (test_root / 'test/trigger/http/HealthControllerTest.java').is_file()
    for name in ('test/infrastructure/persistent', 'test/infrastructure/redis'):
        assert (test_root / name / 'package-info.java').is_file()
    ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
    reactor = ET.parse(project / 'app-backend/pom.xml').getroot()
    managed = reactor.findall('m:dependencyManagement/m:dependencies/m:dependency', ns)
    external = [d for d in managed if not d.findtext('m:artifactId', namespaces=ns).startswith(artifact + '-')]
    assert len(external) == 1
    bom = external[0]
    assert bom.findtext('m:groupId', namespaces=ns) == 'io.github.aut-rain'
    assert bom.findtext('m:artifactId', namespaces=ns) == 'aut-rain-bom'
    assert bom.findtext('m:version', namespaces=ns) == '${aut-rain-bom.version}'
    assert bom.findtext('m:type', namespaces=ns) == 'pom'
    assert bom.findtext('m:scope', namespaces=ns) == 'import'
    assert reactor.findtext('m:properties/m:aut-rain-bom.version', namespaces=ns) == '1.1.0'
    for pom in (project / 'app-backend').rglob('pom.xml'):
        root = ET.parse(pom).getroot()
        group = root.find('m:groupId', ns) if pom.parent.name == 'app-backend' else root.find('m:parent/m:groupId', ns)
        assert group is not None and group.text == group_id, pom
        for dependency in root.findall('.//m:dependency', ns):
            if dependency.findtext('m:artifactId', namespaces=ns).startswith(artifact + '-'):
                assert dependency.findtext('m:groupId', namespaces=ns) == group_id, pom
    for source in (project / 'app-backend').rglob('*.java'):
        content = source.read_text(encoding='utf-8')
        declared = re.search(r'^package ([\w.]+);', content, re.M).group(1)
        assert declared == package or declared.startswith(package + '.'), source
        assert source.parent.as_posix().endswith('/' + declared.replace('.', '/')), source
    resources = project / 'app-backend' / (artifact + '-app') / 'src/main/resources'
    for config in ('application.yml', 'application-dev.yml', 'application-test.yml', 'application-prod.yml', 'banner.txt', 'logback-spring.xml'):
        assert (resources / config).is_file(), config
    for profile in ('dev', 'test', 'prod'):
        assert 'port: ${SERVER_PORT:8080}' in (resources / ('application-' + profile + '.yml')).read_text(encoding='utf-8')
    assert '5137' in (project / 'web/vite.config.ts').read_text(encoding='utf-8')
    check_architecture_boundaries(project, artifact, package)
    java = project / 'app-backend' / (artifact + '-app') / java_path / 'Application.java'
    assert 'package ' + package + ';' in java.read_text(encoding='utf-8')
    app_pom = project / 'app-backend' / (artifact + '-app') / 'pom.xml'
    assert '<mainClass>' + package + '.Application</mainClass>' in app_pom.read_text(encoding='utf-8')
    config = resources / 'application-dev.yml'
    assert '${APP_DB_PASSWORD:123456}' in config.read_text(encoding='utf-8')
    assert '${APP_DB_USERNAME:root}' in config.read_text(encoding='utf-8')
    assert '127.0.0.1:13306/' in config.read_text(encoding='utf-8')
    assert database in config.read_text(encoding='utf-8')
    sql = (project / 'docs/dev-ops/environment/mysql/sql/00-project.sql').read_text(encoding='utf-8')
    assert f'CREATE DATABASE IF NOT EXISTS `{database}`' in sql
    for name in ('docker-compose.yml', 'docker-compose.dev.yml'):
        text = (project / 'docs/dev-ops/environment' / name).read_text(encoding='utf-8')
        assert f'MYSQL_DATABASE: {database}\n' in text
        assert f'MYSQL_USER: {database}\n' in text
    assert f'mysql:3306/{database}?' in (project / 'docs/dev-ops/app/docker-compose.yml').read_text(encoding='utf-8')
    compose = (project / 'docs/dev-ops/app/docker-compose.yml').read_text(encoding='utf-8')
    assert '${MYSQL_PASSWORD:?Configure MYSQL_PASSWORD}' in compose
    assert str(port) in compose
    assert json.loads((project / 'web/package.json').read_text(encoding='utf-8'))['name'] == artifact + '-web'
    for file in project.rglob('*'):
        if not file.is_file():
            continue
        content = file.read_text(encoding='utf-8')
        assert not re.search(r'\$\{(?:artifactId|package|groupId|projectName|databaseName|httpPort|dollar|hash)\}', content), file
        assert '${artifactId.' not in content, file
        assert not re.search(r'__(?:artifactId|packageInPathFormat)__', str(file)), file
        assert '192.168.0.196' not in content, file
        if file.suffix == '.py':
            compile(content, str(file), 'exec')
    print('Generated structure, parameter substitution and runtime placeholders passed.', flush=True)
    check_compose(project / 'docs/dev-ops')


def check_compose(ops):
    """Resolve Compose without contacting Docker daemon or starting services."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith('COMPOSE_') and key != 'IMAGE_TAG'}
    keys = ('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'REDIS_PASSWORD', 'REDIS_ADMIN_PASSWORD',
            'NACOS_AUTH_IDENTITY_VALUE', 'XXL_JOB_ACCESS_TOKEN', 'RUSTFS_ACCESS_KEY', 'RUSTFS_SECRET_KEY')
    env.update({key: 'VerificationOnly_' + key + '_12345678901234567890' for key in keys})
    env.update(NACOS_AUTH_TOKEN='MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVm',
               IMAGE_TAG='verification', HTTP_BIND='0.0.0.0', HTTP_PORT='80',
               MYSQL_PORT='3306', BROKER_ADVERTISE_HOST='127.0.0.1')
    prefix = [tool('docker'), 'compose', '--env-file', os.devnull,
              '--project-directory', str((ops / 'environment').resolve()),
              '-f', str((ops / 'environment/docker-compose.yml').resolve())]
    def config(files):
        result = subprocess.run(prefix + files + ['config', '--format', 'json'], env=env,
                                check=True, capture_output=True, text=True)
        return json.loads(result.stdout)
    prod = config(['-f', str((ops / 'app/docker-compose.yml').resolve())])
    expected = {'mysql', 'redis', 'nacos', 'rocketmq-namesrv', 'rocketmq-broker', 'xxl-job-admin', 'rustfs'}
    baseline = {'mysql': 'mysql:8.0.32', 'redis': 'redis:6.2', 'rustfs': 'rustfs/rustfs:1.0.4',
                'nacos': 'nacos/nacos-server:v3.0.3',
                'rocketmq-namesrv': 'apache/rocketmq:5.1.0',
                'rocketmq-broker': 'apache/rocketmq:5.1.0',
                'xxl-job-admin': 'xuxueli/xxl-job-admin:2.4.1'}
    assert set(prod['services']) == expected | {'app', 'nginx'}
    assert set(prod['networks']) == {'autrain-network'}
    assert prod['networks']['autrain-network']['driver'] == 'bridge'
    assert prod['networks']['autrain-network']['name'] == 'autrain-network'
    for service in prod['services'].values():
        assert set(service['networks']) == {'autrain-network'}
    for name in expected:
        assert prod['services'][name]['image'] == baseline[name], name
        assert not prod['services'][name].get('ports'), name
        assert 'healthcheck' in prod['services'][name], name
    rustfs = prod['services']['rustfs']
    assert rustfs['environment']['RUSTFS_ACCESS_KEY'] == env['RUSTFS_ACCESS_KEY']
    assert rustfs['environment']['RUSTFS_SECRET_KEY'] == env['RUSTFS_SECRET_KEY']
    assert {(v['source'], v['target']) for v in rustfs['volumes']} == {('rustfs-data', '/data'), ('rustfs-logs', '/logs')}
    assert all(v['type'] == 'volume' for v in rustfs['volumes'])
    assert '/health' in rustfs['healthcheck']['test'][-1]
    assert '/rustfs/console/health' in rustfs['healthcheck']['test'][-1]
    nacos = prod['services']['nacos']
    assert nacos['environment']['SPRING_DATASOURCE_PLATFORM'] == 'mysql'
    for key in ('NACOS_AUTH_ENABLE', 'NACOS_AUTH_ADMIN_ENABLE', 'NACOS_AUTH_CONSOLE_ENABLE'):
        assert nacos['environment'][key] == 'true'
    assert nacos['healthcheck']['test'][-1].endswith('/nacos/v3/admin/core/state/readiness')
    schema = (ops / 'environment/mysql/sql/nacos.sql').read_text(encoding='utf-8')
    assert 'CREATE TABLE `config_info_gray`' in schema
    assert '`publish_type`' in schema and '`ext_info`' in schema
    assert prod['services']['nginx']['ports'][0]['published'] == '80'
    assert prod['services']['nginx']['ports'][0]['target'] == 80
    for service in prod['services'].values():
        for mount in service.get('volumes', []):
            if mount['type'] == 'bind':
                assert Path(mount['source']).exists(), mount
        if 'build' in service:
            build = service['build']
            project = ops.parents[1]
            context = Path(build['context']).resolve()
            dockerfile = context / build['dockerfile']
            assert dockerfile.is_file(), dockerfile
            if service['image'].split(':')[0].endswith('/app'):
                assert context.parent == project / 'app-backend'
                assert context.name.endswith('-app')
                assert (context / '.dockerignore').is_file()
            else:
                assert context == project
                assert build['dockerfile'] == 'docs/dev-ops/environment/nginx/Dockerfile'
                assert 'COPY web/dist/' in dockerfile.read_text(encoding='utf-8')
                assert dockerfile.with_name('Dockerfile.dockerignore').is_file()
    assert not prod['services']['nginx'].get('volumes'), 'Frontend assets must be in the image'
    for sql in ('nacos.sql', 'xxl-job.sql'):
        assert not re.search(r'FOREIGN\s+KEY', (ops / 'environment/mysql/sql' / sql).read_text(encoding='utf-8'), re.I)
    assert not (ops / 'environment/mysql/initdb').exists()
    assert not (ops / 'environment/sql').exists()
    mounts = [mount for mount in prod['services']['mysql']['volumes']
              if mount['target'].startswith('/docker-entrypoint-initdb.d')]
    assert len(mounts) == 1 and mounts[0]['target'] == '/docker-entrypoint-initdb.d'
    assert Path(mounts[0]['source']) == ops / 'environment/mysql/sql'
    assert mounts[0]['read_only']
    for filename, database in (('nacos.sql', 'nacos_config'), ('xxl-job.sql', 'xxl_job')):
        sql = (ops / 'environment/mysql/sql' / filename).read_text(encoding='utf-8')
        assert f'CREATE DATABASE IF NOT EXISTS `{database}`' in sql
        assert sql.index(f'USE `{database}`;') < sql.index('CREATE TABLE')
        assert '$' not in sql, 'Initialization SQL must not depend on shell expansion'
    xxl_sql = (ops / 'environment/mysql/sql/xxl-job.sql').read_text(encoding='utf-8')
    assert "VALUES ('admin', 'e10adc3949ba59abbe56e057f20f883e', 1, NULL)" in xxl_sql
    mysql_env = prod['services']['mysql']['environment']
    assert mysql_env['MYSQL_ROOT_HOST'] == '%'
    assert nacos['environment']['MYSQL_SERVICE_USER'] == 'root'
    assert nacos['environment']['MYSQL_SERVICE_PASSWORD'] == mysql_env['MYSQL_ROOT_PASSWORD']
    xxl_env = prod['services']['xxl-job-admin']['environment']
    assert xxl_env['SPRING_DATASOURCE_USERNAME'] == 'root'
    assert xxl_env['SPRING_DATASOURCE_PASSWORD'] == mysql_env['MYSQL_ROOT_PASSWORD']
    dev_file = ops / 'environment/docker-compose.dev.yml'
    if dev_file.exists():
        # Development is standalone: it must not inherit production image tags or volumes.
        dev_prefix = prefix[:-2] + ['-f', str(dev_file.resolve())]
        dev_env = {key: value for key, value in env.items()
                   if key not in keys and key not in ('NACOS_AUTH_TOKEN', 'BROKER_ADVERTISE_HOST',
                       'MYSQL_PORT', 'REDIS_PORT', 'NACOS_CONSOLE_PORT', 'XXL_JOB_PORT',
                       'PHPMYADMIN_PORT', 'REDIS_ADMIN_PORT', 'ROCKETMQ_DASHBOARD_PORT',
                       'RUSTFS_API_PORT', 'RUSTFS_CONSOLE_PORT')}
        result = subprocess.run(dev_prefix + ['config', '--format', 'json'], env=dev_env,
                                check=True, capture_output=True, text=True)
        dev = json.loads(result.stdout)
        assert set(dev['networks']) == {'autrain-network'}
        assert dev['networks']['autrain-network']['driver'] == 'bridge'
        assert dev['networks']['autrain-network']['name'] == 'autrain-network'
        for name, service in dev['services'].items():
            if name != 'rocketmq-dashboard':
                assert set(service['networks']) == {'autrain-network'}
        assert dev['services']['mysql']['environment']['MYSQL_ROOT_PASSWORD'] == '123456'
        assert dev['services']['mysql']['environment']['MYSQL_ROOT_HOST'] == '%'
        assert dev['services']['xxl-job-admin']['environment']['SPRING_DATASOURCE_PASSWORD'] == '123456'
        assert dev['services']['xxl-job-admin']['environment']['XXL_JOB_ACCESS_TOKEN'] == 'default_token'
        rustfs_dev = dev['services']['rustfs']
        assert rustfs_dev['environment']['RUSTFS_ACCESS_KEY'] == 'rustfsadmin'
        assert rustfs_dev['environment']['RUSTFS_SECRET_KEY'] == 'rustfsadmin'
        assert rustfs_dev['volumes'] == rustfs['volumes']
        redis = dev['services']['redis']
        assert 'REDIS_PASSWORD' not in redis.get('environment', {})
        assert '--requirepass' not in redis['command']
        assert redis['command'][-2:] == ['--protected-mode', 'no']
        assert redis['healthcheck']['test'] == ['CMD', 'redis-cli', 'ping']
        assert 'REDIS_PASSWORD' not in dev['services']['redis-admin']['environment']
        assert dev['services']['redis-admin']['environment']['HTTP_PASSWORD'] == 'admin'
        versions = {'mysql': 'mysql:8.0.32', 'redis': 'redis:6.2', 'rustfs': 'rustfs/rustfs:1.0.4',
                    'nacos': 'nacos/nacos-server:v3.0.3',
                    'rocketmq-namesrv': 'apache/rocketmq:5.1.0',
                    'rocketmq-broker': 'apache/rocketmq:5.1.0',
                    'xxl-job-admin': 'xuxueli/xxl-job-admin:2.4.1',
                    'phpmyadmin': 'phpmyadmin:5.2.1',
                    'redis-admin': 'spryker/redis-commander:0.8.0',
                    'rocketmq-dashboard': 'apacherocketmq/rocketmq-dashboard:1.0.0'}
        assert set(dev['services']) == set(versions)
        for name, image in versions.items():
            assert dev['services'][name]['image'] == image, name
        for name in expected:
            assert dev['services'][name]['image'] == prod['services'][name]['image'], name
        published = []
        for service in dev['services'].values():
            assert all(port['host_ip'] == '127.0.0.1' for port in service.get('ports', []))
            published.extend(port['published'] for port in service.get('ports', []))
            for mount in service.get('volumes', []):
                if mount['type'] == 'bind':
                    assert Path(mount['source']).is_file(), mount
                    assert mount['read_only'], mount
        assert len(published) == len(set(published)), 'Development port collision'
        assert all(1 <= int(port) <= 65535 for port in published)
        expected_ports = {
            'mysql': {(13306, 3306)}, 'redis': {(16379, 6379)},
            'rustfs': {(19000, 9000), (19001, 9001)},
            'nacos': {(18848, 8848), (19848, 9848), (19849, 9849), (18080, 8080)},
            'xxl-job-admin': {(19090, 9090)}, 'phpmyadmin': {(18899, 80)},
            'redis-admin': {(18081, 8081)}, 'rocketmq-namesrv': {(19876, 9876)},
            'rocketmq-broker': {(20909, 20909), (20911, 20911), (20912, 20912), (18082, 8080)},
            'rocketmq-dashboard': set(),
        }
        for name, ports in expected_ports.items():
            actual = {(int(p['published']), p['target']) for p in dev['services'][name].get('ports', [])}
            assert actual == ports, (name, actual)
        broker_command = ' '.join(dev['services']['rocketmq-broker']['command'])
        assert 'listenPort=20911' in broker_command and 'haListenPort=20912' in broker_command
        assert '8080' not in published and '5137' not in published
        assert dev['services']['nacos']['environment']['MODE'] == 'standalone'
        assert 'SPRING_DATASOURCE_PLATFORM' not in dev['services']['nacos']['environment']
        assert dev['services']['rocketmq-dashboard']['network_mode'] == 'service:rocketmq-broker'
        assert dev['services']['rocketmq-broker']['environment']['BROKER_ADVERTISE_HOST'] == '127.0.0.1'
        assert dev['name'] != prod['name']
        assert not ({volume['name'] for volume in dev['volumes'].values()} &
                    {volume['name'] for volume in prod['volumes'].values()})
        init_mounts = [mount for mount in dev['services']['mysql']['volumes']
                       if mount['target'].startswith('/docker-entrypoint-initdb.d')]
        assert {mount['target'] for mount in init_mounts} == {'/docker-entrypoint-initdb.d/00-project.sql', '/docker-entrypoint-initdb.d/xxl-job.sql'}
        for mount in init_mounts:
            assert Path(mount['source']) == ops / 'environment/mysql/sql' / Path(mount['target']).name
        assert dev['services']['xxl-job-admin']['environment']['SPRING_DATASOURCE_USERNAME'] == 'root'
        # Only the development file is passed, including when local default ports are occupied.
        result = subprocess.run(dev_prefix + ['config', '--format', 'json'],
                                env={**dev_env, 'MYSQL_PORT': '23306', 'NACOS_CONSOLE_PORT': '28080',
                                     'MYSQL_ROOT_PASSWORD': 'OverrideForVerification'},
                                check=True, capture_output=True, text=True)
        custom = json.loads(result.stdout)
        assert custom['services']['mysql']['ports'][0]['published'] == '23306'
        assert custom['services']['mysql']['environment']['MYSQL_ROOT_PASSWORD'] == 'OverrideForVerification'
        assert custom['services']['xxl-job-admin']['environment']['SPRING_DATASOURCE_PASSWORD'] == 'OverrideForVerification'
        assert any(p['published'] == '28080' and p['target'] == 8080
                   for p in custom['services']['nacos']['ports'])
    assert prod['services']['rocketmq-broker']['environment']['BROKER_ADVERTISE_HOST'] == 'rocketmq-broker'
    print('Compose services, networks, ports, bind paths and build paths passed (no daemon).', flush=True)


def check_architecture_boundaries(project, artifact, package):
    """Keep module dependencies aligned with the generated DDD package boundaries."""
    source_root = project / 'app-backend'
    # Check Maven dependencies too: source-only checks miss an unused forbidden dependency.
    allowed = {
        'types': set(), 'api': {'types'}, 'domain': {'types'},
        'infrastructure': {'domain'}, 'trigger': {'api', 'domain', 'types'},
        'app': {'trigger', 'infrastructure'},
    }
    ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
    for module, expected in allowed.items():
        pom = ET.parse(source_root / (artifact + '-' + module) / 'pom.xml')
        dependencies = {item.findtext('m:artifactId', namespaces=ns)
                        for item in pom.findall('m:dependencies/m:dependency', ns)}
        internal = {name[len(artifact) + 1:] for name in dependencies if name.startswith(artifact + '-')}
        assert internal == expected, (module, internal, expected)
    forbidden = {
        'types': ('api.', 'domain.', 'infrastructure.', 'trigger.'),
        'api': ('domain.', 'infrastructure.', 'trigger.'),
        'domain': ('infrastructure.', 'trigger.'),
        'infrastructure': ('trigger.',),
        'trigger': ('infrastructure.',),
    }
    for module, suffixes in forbidden.items():
        java_root = source_root / (artifact + '-' + module) / 'src/main/java'
        for file in java_root.rglob('*.java'):
            content = file.read_text(encoding='utf-8')
            for suffix in suffixes:
                assert f'import {package}.{suffix}' not in content, f'{module} imports {suffix}: {file}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-only', action='store_true', help='Validate generation and backend without frontend builds')
    parser.add_argument('--maven', help='Maven executable, e.g. the Maven bundled with IDEA')
    parser.add_argument('--settings', help='Maven settings.xml used by the IDE')
    parser.add_argument('--local-repository', help='Maven local repository used by the IDE')
    args = parser.parse_args()
    mvn = args.maven or tool('mvn')
    maven = [mvn, '-B', '-ntp']
    if args.settings:
        maven += ['-s', args.settings]
    if args.local_repository:
        maven += ['-Dmaven.repo.local=' + args.local_repository]
    output = ROOT / 'target' / ('verification-' + uuid.uuid4().hex[:8])
    run(maven + ['clean', 'install'], ROOT)
    output.mkdir(parents=True)
    generate = maven + ['org.apache.maven.plugins:maven-archetype-plugin:3.4.1:generate',
             '-DarchetypeCatalog=local', '-DarchetypeGroupId=com.autrain',
             '-DarchetypeArtifactId=aut-rain-ddd-archetype', '-DarchetypeVersion=1.0.0',
             '-Dversion=0.1.0-SNAPSHOT',
             '-DoutputDirectory=' + str(output), '-DinteractiveMode=false']
    for artifact, database, port in [('sample-service', 'sample_data', 5137), ('another-service', 'another_data', 5138)]:
        explicit = [] if artifact == 'sample-service' else ['-DgroupId=io.example.orders']
        run(generate + ['-DartifactId=' + artifact,
             '-DdatabaseName=' + database, '-DhttpPort=' + str(port),
             *explicit], output)
        inspect(output / artifact, artifact, database, port,
                'com.autrain' if artifact == 'sample-service' else 'io.example.orders')
    # Reproduce IDEA's literal default expressions and org.example wizard default.
    for artifact, properties, group_id, root_package in [
        ('idea-literal', ['-DgroupId=org.example', "-Dpackage=com.rain.${artifactId.replace('-', '_')}", '-DprojectName=${artifactId}'], 'org.example', None),
        ('idea-default', ['-DgroupId=org.example', '-Dpackage=com.rain'], 'org.example', None),
        ('bare-package', ['-Dpackage'], 'com.autrain', None),
        ('project-template', [], 'com.autrain', None),
        ('group-hyphen', ['-DgroupId=io.example.my-company'], 'io.example.my-company', None),
        ('explicit-package', ['-DgroupId=com.autrain', '-Dpackage=cn.im9sunnyboy'], 'com.autrain', 'cn.im9sunnyboy'),
    ]:
        run(generate + ['-DartifactId=' + artifact, *properties], output)
        inspect(output / artifact, artifact, artifact.replace('-', '_'), 80, group_id, root_package)
    for artifact, properties, message in [
        ('class', [], 'artifactId cannot be a Java reserved name'),
        ('bad_name', [], 'artifactId must contain 2-40'),
        ('invalid-group', ['-DgroupId=com.1bad'], 'groupId must form a valid Java package'),
        ('reserved-group', ['-DgroupId=com.class'], 'groupId segment cannot be a Java reserved name'),
        ('invalid-package', ['-Dpackage=cn.1bad'], 'package must be a valid Java package'),
        ('reserved-package', ['-Dpackage=cn.class'], 'package segment cannot be a Java reserved name'),
    ]:
        result = subprocess.run(generate + ['-DartifactId=' + artifact, *properties], cwd=output,
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert result.returncode != 0, 'Invalid generation parameters were accepted: ' + artifact
        assert message in result.stdout + result.stderr, result.stdout + result.stderr
        print('Rejected invalid generation parameters: ' + artifact, flush=True)
    project = output / 'sample-service'
    from check_app_scripts import check_app_scripts
    check_app_scripts(project)
    run(maven + ['-f', 'app-backend/pom.xml', 'clean', 'package'], project)
    run(maven + ['-f', 'app-backend/pom.xml', 'clean', 'package'], output / 'idea-literal')
    run(maven + ['-f', 'app-backend/pom.xml', 'clean', 'package'], output / 'another-service')
    if args.backend_only:
        print('PASSED. Generated examples retained at: ' + str(output))
        print('No application, database, Docker service or deployment was started.')
        return
    corepack = tool('corepack')
    run([corepack, 'pnpm', 'install', '--frozen-lockfile'], project / 'web')
    for task in ('typecheck', 'lint', 'test', 'build'):
        run([corepack, 'pnpm', task], project / 'web')
    print('PASSED. Generated examples retained at: ' + str(output))
    print('No application, database, Docker service or deployment was started.')


if __name__ == '__main__':
    main()
