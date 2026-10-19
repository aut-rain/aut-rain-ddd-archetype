"""Generate and validate a project without starting any services. Requires Python 3.12+."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tarfile
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


def inspect(project, artifact, database, port):
    package = 'com.rain.' + artifact.replace('-', '_')
    java_path = 'src/main/java/' + package.replace('.', '/')
    expected = ['app-backend/pom.xml', '.gitignore', '.editorconfig', '.env.example', '.gitattributes',
                'README.md', 'web/package.json', 'web/pnpm-lock.yaml', 'docs/dev-ops/environment/docker-compose.yml',
                'docs/dev-script/deployment/deploy/first-deploy.sh']
    for name in expected:
        assert (project / name).is_file(), name
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
    external = [d for d in managed if d.findtext('m:groupId', namespaces=ns) != 'com.autrain']
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
        assert group is not None and group.text == 'com.autrain', pom
        for dependency in root.findall('.//m:dependency', ns):
            if dependency.findtext('m:artifactId', namespaces=ns).startswith(artifact + '-'):
                assert dependency.findtext('m:groupId', namespaces=ns) == 'com.autrain', pom
    for source in (project / 'app-backend').rglob('*.java'):
        content = source.read_text(encoding='utf-8')
        declared = re.search(r'^package ([\w.]+);', content, re.M).group(1)
        assert declared == package or declared.startswith(package + '.'), source
        assert source.parent.as_posix().endswith('/' + declared.replace('.', '/')), source
    resources = project / 'app-backend' / (artifact + '-app') / 'src/main/resources'
    for config in ('application.yml', 'application-dev.yml', 'application-test.yml', 'application-prod.yml', 'banner.txt', 'logback-spring.xml'):
        assert (resources / config).is_file(), config
    for profile in ('dev', 'test', 'prod'):
        assert 'port: ${SERVER_PORT:8080}' in (resources / ('application-' + profile + '.yml')).read_text()
    assert '5137' in (project / 'web/vite.config.ts').read_text()
    check_architecture_boundaries(project, artifact)
    java = project / 'app-backend' / (artifact + '-app') / java_path / 'Application.java'
    assert 'package ' + package + ';' in java.read_text()
    app_pom = project / 'app-backend' / (artifact + '-app') / 'pom.xml'
    assert '<mainClass>' + package + '.Application</mainClass>' in app_pom.read_text()
    config = resources / 'application-dev.yml'
    assert '${APP_DB_PASSWORD}' in config.read_text()
    assert database in config.read_text()
    compose = (project / 'docs/dev-ops/app/docker-compose.yml').read_text(encoding='utf-8')
    assert '${MYSQL_PASSWORD:?Configure MYSQL_PASSWORD}' in compose
    assert str(port) in compose
    assert json.loads((project / 'web/package.json').read_text())['name'] == artifact + '-web'
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
           if not key.startswith('COMPOSE_') and key not in ('APP_RELEASE_ID', 'WEB_RELEASE_ID')}
    keys = ('MYSQL_PASSWORD', 'MYSQL_ROOT_PASSWORD', 'REDIS_PASSWORD', 'NACOS_DB_PASSWORD',
            'NACOS_AUTH_IDENTITY_VALUE', 'XXL_JOB_DB_PASSWORD', 'XXL_JOB_ACCESS_TOKEN', 'XXL_JOB_ADMIN_PASSWORD')
    env.update({key: 'VerificationOnly_' + key + '_12345678901234567890' for key in keys})
    env.update(NACOS_AUTH_TOKEN='MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVm',
               RELEASE_ID='verification', WEB_ROOT=str(ops.resolve()), HTTP_BIND='0.0.0.0', HTTP_PORT='80',
               MYSQL_PORT='3306', BROKER_ADVERTISE_HOST='127.0.0.1')
    prefix = [tool('docker'), 'compose', '--env-file', os.devnull,
              '--project-directory', str((ops / 'environment').resolve()),
              '-f', str((ops / 'environment/docker-compose.yml').resolve())]
    def config(files):
        result = subprocess.run(prefix + files + ['config', '--format', 'json'], env=env,
                                check=True, capture_output=True, text=True)
        return json.loads(result.stdout)
    prod = config(['-f', str((ops / 'app/docker-compose.yml').resolve())])
    expected = {'mysql', 'redis', 'nacos', 'rocketmq-namesrv', 'rocketmq-broker', 'xxl-job-admin'}
    assert set(prod['services']) == expected | {'app', 'nginx'}
    for name in expected:
        assert not prod['services'][name].get('ports'), name
        assert 'healthcheck' in prod['services'][name], name
    assert prod['services']['nginx']['ports'][0]['published'] == '80'
    assert prod['services']['nginx']['ports'][0]['target'] == 80
    for service in prod['services'].values():
        for mount in service.get('volumes', []):
            if mount['type'] == 'bind':
                assert Path(mount['source']).exists(), mount
        if 'build' in service:
            build = service['build']
            assert Path(build['context']).resolve() == ops.resolve()
            dockerfile = Path(build['context']) / build['dockerfile']
            if build['dockerfile'] == 'app/Dockerfile' and (ops.parents[1] / 'app-backend').is_dir():
                candidates = list((ops.parents[1] / 'app-backend').glob('*-app/Dockerfile'))
                assert len(candidates) == 1, candidates
                dockerfile = candidates[0]
            assert dockerfile.is_file(), dockerfile
            if build['dockerfile'] == 'app/Dockerfile':
                assert build['args']['JAR_FILE'] == 'app.jar'
    for sql in ('nacos.sql', 'xxl-job.sql'):
        assert not re.search(r'FOREIGN\s+KEY', (ops / 'environment/sql' / sql).read_text(encoding='utf-8'), re.I)
    dev_file = ops / 'environment/docker-compose.dev.yml'
    if dev_file.exists():
        dev = config(['-f', str(dev_file.resolve())])
        assert set(dev['services']) == expected
        for service in dev['services'].values():
            assert all(port['host_ip'] == '127.0.0.1' for port in service.get('ports', []))
        assert dev['services']['rocketmq-broker']['environment']['BROKER_ADVERTISE_HOST'] == '127.0.0.1'
    assert prod['services']['rocketmq-broker']['environment']['BROKER_ADVERTISE_HOST'] == 'rocketmq-broker'
    print('Compose services, networks, ports, bind paths and build paths passed (no daemon).', flush=True)


def check_architecture_boundaries(project, artifact):
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
                package = 'com.rain.' + artifact.replace('-', '_')
                assert f'import {package}.{suffix}' not in content, f'{module} imports {suffix}: {file}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-only', action='store_true', help='Validate generation and backend without frontend/delivery builds')
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
        explicit = [] if artifact == 'sample-service' else ['-DgroupId=com.autrain', '-Dpackage=com.rain.another_service']
        run(generate + ['-DartifactId=' + artifact,
             '-DdatabaseName=' + database, '-DhttpPort=' + str(port),
             *explicit], output)
        inspect(output / artifact, artifact, database, port)
    # Reproduce IDEA's literal default expressions and org.example wizard default.
    for artifact, properties in [
        ('idea-literal', ['-DgroupId=org.example', "-Dpackage=com.rain.${artifactId.replace('-', '_')}", '-DprojectName=${artifactId}']),
        ('idea-default', ['-DgroupId=org.example', '-Dpackage=com.rain']),
        ('bare-package', ['-Dpackage']),
        ('project-template', []),
    ]:
        run(generate + ['-DartifactId=' + artifact, *properties], output)
        inspect(output / artifact, artifact, 'app_db', 80)
    for artifact, properties, message in [
        ('class', [], 'artifactId cannot be a Java reserved name'),
        ('bad_name', [], 'artifactId must contain 2-40'),
    ]:
        result = subprocess.run(generate + ['-DartifactId=' + artifact, *properties], cwd=output,
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert result.returncode != 0, 'Invalid generation parameters were accepted: ' + artifact
        assert message in result.stdout + result.stderr, result.stdout + result.stderr
        print('Rejected invalid generation parameters: ' + artifact, flush=True)
    project = output / 'sample-service'
    run(maven + ['-f', 'app-backend/pom.xml', 'clean', 'package'], project)
    run(maven + ['-f', 'app-backend/pom.xml', 'clean', 'package'], output / 'idea-literal')
    if args.backend_only:
        print('PASSED. Generated examples retained at: ' + str(output))
        print('No application, database, Docker service or deployment was started.')
        return
    corepack = tool('corepack')
    run([corepack, 'pnpm', 'install', '--frozen-lockfile'], project / 'web')
    for task in ('typecheck', 'lint', 'test', 'build'):
        run([corepack, 'pnpm', task], project / 'web')
    run([sys.executable, '-m', 'unittest', 'discover', '-s', 'docs/dev-script/deployment/tests', '-p', 'test_*.py'], project)
    code = "import sys; sys.path.insert(0, 'docs/dev-script/deployment/prepare'); import build_upload; p=build_upload.pack(); print(build_upload.verify_archive(p))"
    run([sys.executable, '-c', code], project)
    package = max((project / '.runtime/delivery').glob('*.tar.gz'), key=lambda p: p.stat().st_mtime)
    with tempfile.TemporaryDirectory() as temp:
        with tarfile.open(package) as archive:
            archive.extractall(temp, filter='data')
        release = next(Path(temp).iterdir())
        check_compose(release)
    print('PASSED. Generated examples retained at: ' + str(output))
    print('No application, database, Docker service or deployment was started.')


if __name__ == '__main__':
    main()
