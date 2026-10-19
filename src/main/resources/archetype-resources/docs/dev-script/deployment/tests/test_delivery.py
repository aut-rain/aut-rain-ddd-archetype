#set( $dollar = '$' )
#set( $hash = '#' )
"""Run: python -m unittest discover -s docs/dev-script/deployment/tests -p test_*.py"""
import json
import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'lib'))
sys.path.insert(0, str(HERE.parent / 'prepare'))
import build_upload
import bootstrap_server
import delivery
import server


class DeliveryTests(unittest.TestCase):
    def fixture(self, root):
        stage = root / 'release-123'
        stage.mkdir()
        for name in delivery.DEPLOY_FILES:
            (stage / name).parent.mkdir(parents=True, exist_ok=True)
            (stage / name).write_text('example\n')
        (stage / 'web/assets').mkdir(parents=True)
        (stage / 'web/index.html').write_text('<script src="/assets/app.js"></script>')
        (stage / 'web/assets/app.js').write_text('console.log("sample");')
        migration = b'SELECT 1;'
        with zipfile.ZipFile(stage / 'app.jar', 'w') as jar:
            jar.writestr('BOOT-INF/classes/application-prod.yml', 'spring: {}')
            jar.writestr('BOOT-INF/classes/db/migration/V1__example.sql', migration)
        import hashlib
        manifest = {'application': '${artifactId}', 'release_id': stage.name,
                    'migrations': {'V1__example.sql': hashlib.sha256(migration).hexdigest()},
                    'files': {p.relative_to(stage).as_posix(): delivery.digest(p) for p in stage.rglob('*') if p.is_file()}}
        (stage / 'release.json').write_text(json.dumps(manifest))
        return stage

    def test_release_and_archive_checksums_and_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = self.fixture(root)
            self.assertEqual(delivery.verify_release(stage)['release_id'], stage.name)
            package = root / (stage.name + '.tar.gz')
            with tarfile.open(package, 'w:gz') as archive:
                archive.add(stage, arcname=stage.name)
            Path(str(package) + '.sha256').write_text(delivery.digest(package))
            self.assertEqual(build_upload.verify_archive(package), stage.name)
            bootstrap_server.install(package, root / 'server')
            with self.assertRaises(FileExistsError):
                bootstrap_server.install(package, root / 'server')
            (stage / 'web/assets/app.js').write_text('altered')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                delivery.verify_release(stage)
            package.write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                build_upload.verify_archive(package)

    def test_rejects_traversal_and_special_archive_members(self):
        for name in ('../escape', '/etc/passwd', 'web/../../secret', 'C:\\secret'):
            with self.assertRaises(ValueError):
                delivery.relative_file(name)
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / 'release-123.tar.gz'
            with tarfile.open(package, 'w:gz') as archive:
                link = tarfile.TarInfo('release-123/link')
                link.type = tarfile.SYMTYPE
                link.linkname = '/etc/passwd'
                archive.addfile(link)
            Path(str(package) + '.sha256').write_text(delivery.digest(package))
            with self.assertRaisesRegex(ValueError, 'link or special'):
                build_upload.verify_archive(package)

    def test_stale_migrations_and_development_assets_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self.fixture(Path(tmp))
            manifest = json.loads((stage / 'release.json').read_text())
            with self.assertRaisesRegex(ValueError, 'Migration checksum'):
                delivery.check_payload(stage, {'V1__example.sql': '0' * 64})
            (stage / 'web/assets/app.js').write_text('http://127.0.0.1:5137/')
            with self.assertRaisesRegex(ValueError, 'Development address'):
                delivery.check_payload(stage, manifest['migrations'])

    def test_init_never_overwrites_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(server, 'WEB_ROOT', root / 'web'):
                server.initialize(root, ${httpPort}, '0.0.0.0')
            first = (root / '.env').read_bytes()
            with self.assertRaises(FileExistsError):
                with patch.object(server, 'WEB_ROOT', root / 'web'):
                    server.initialize(root, 18081, '0.0.0.0')
            self.assertEqual(first, (root / '.env').read_bytes())

    def test_backup_failure_blocks_app_start_and_does_not_delete_data(self):
        deployment = object.__new__(server.Deployment)
        deployment.validate_mode = lambda mode: None
        deployment.record_attempt = lambda mode: None
        deployment.env = {}
        deployment.manifest = {'release_id': 'test-release'}
        deployment.publish_frontend = lambda: None
        calls = []
        deployment.compose = lambda *args, **kwargs: calls.append(args)
        deployment.sql = lambda query: '10'
        deployment.backup = lambda: (_ for _ in ()).throw(RuntimeError('backup failed'))
        with self.assertRaisesRegex(RuntimeError, 'backup failed'):
            deployment.deploy()
        self.assertEqual(calls[-1], ('stop', 'nginx', 'app'))
        self.assertFalse(any('--force-recreate' in call or 'down' in call for call in calls))

    def test_missing_upload_target_fails_before_build(self):
        with patch('sys.argv', ['build_upload.py']), patch.object(build_upload, 'build') as build:
            with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit):
                build_upload.main()
            build.assert_not_called()

    def test_pack_copies_layered_configuration_and_excludes_local_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self.fixture(root)
            docs = root / 'docs'
            ops = docs / 'dev-ops'
            for destination, source in delivery.DEPLOY_FILES.items():
                path = root / source
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(('content: ' + source + '\r\n').encode('utf-8-sig'))
            (ops / 'environment/.env').write_text('secret credentials')
            (ops / 'environment/docker-compose.dev.yml').write_text('development only')
            jar = root / 'app-backend/${artifactId}-app/target/${artifactId}-app.jar'
            jar.parent.mkdir(parents=True)
            jar.write_bytes((fixture / 'app.jar').read_bytes())
            migrations = root / 'app-backend/${artifactId}-app/src/main/resources/db/migration'
            migrations.mkdir(parents=True)
            (migrations / 'V1__example.sql').write_bytes(b'SELECT 1;')
            import shutil
            shutil.copytree(fixture / 'web', root / 'web/dist')
            with patch.object(build_upload, 'ROOT', root), \
                    patch.object(build_upload, 'tool', return_value='git'), \
                    patch.object(build_upload, 'run', side_effect=['revision\n', '']):
                package = build_upload.pack()
                backend_dockerfile = root / delivery.DEPLOY_FILES['app/Dockerfile']
                original = backend_dockerfile.read_bytes()
                backend_dockerfile.write_text('changed backend image')
                with self.assertRaisesRegex(ValueError, 'Unselected'):
                    build_upload.pack('frontend', package)
                backend_package = build_upload.pack('backend', package)
                build_upload.verify_archive(backend_package)
                backend_dockerfile.write_bytes(original)
                nginx_config = root / delivery.DEPLOY_FILES['environment/nginx/conf.d/default.conf']
                nginx_original = nginx_config.read_bytes()
                nginx_config.write_text('changed nginx config')
                with self.assertRaisesRegex(ValueError, 'Unselected'):
                    build_upload.pack('backend', package)
                frontend_package = build_upload.pack('frontend', package)
                build_upload.verify_archive(frontend_package)
                nginx_config.write_bytes(nginx_original)
                middleware = root / delivery.DEPLOY_FILES['environment/redis/redis.conf']
                middleware.write_text('changed redis config')
                for component in ('frontend', 'backend'):
                    with self.assertRaisesRegex(ValueError, 'Unselected'):
                        build_upload.pack(component, package)
                self.assertEqual(len(list((root / '.runtime/delivery').glob('*.tar.gz'))), 3)
            build_upload.verify_archive(package)
            with tarfile.open(package, 'r:gz') as archive:
                release = package.name.removesuffix('.tar.gz')
                names = {m.name.removeprefix(release + '/') for m in archive.getmembers() if m.isfile()}
                self.assertTrue(set(delivery.DEPLOY_FILES).issubset(names))
                self.assertNotIn('environment/docker-compose.dev.yml', names)
                self.assertNotIn('environment/.env', names)
                self.assertNotIn('compose.yaml', names)
                for destination, source in delivery.DEPLOY_FILES.items():
                    member = archive.getmember(release + '/' + destination)
                    self.assertEqual(member.mode, 0o644)
                    self.assertEqual(archive.extractfile(member).read(), ('content: ' + source + '\n').encode())

    def test_missing_backend_dockerfile_fails_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for source in delivery.DEPLOY_FILES.values():
                path = root / source
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            (root / 'app-backend/${artifactId}-app/Dockerfile').unlink()
            with patch.object(build_upload, 'ROOT', root), patch.object(build_upload, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'Missing deployment source: app-backend/.*/Dockerfile'):
                    build_upload.build()
                run.assert_not_called()

    def test_server_combines_production_and_application_compose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            releases = root / 'releases'
            releases.mkdir()
            stage = self.fixture(releases)
            with patch.object(server, 'RELEASE', stage), patch.object(server, 'configuration', return_value={}):
                deployment = server.Deployment(root)
            files = [deployment.prefix[i + 1] for i, arg in enumerate(deployment.prefix) if arg == '-f']
            self.assertEqual(files, [str(stage / 'environment/docker-compose.yml'), str(stage / 'app/docker-compose.yml')])


if __name__ == '__main__':
    unittest.main()
