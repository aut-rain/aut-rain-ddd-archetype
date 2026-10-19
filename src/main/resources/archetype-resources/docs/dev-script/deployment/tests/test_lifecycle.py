#set( $dollar = '$' )
#set( $hash = '#' )
"""Lifecycle behavior tests: no real Docker calls or production resources."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
import host
import server
import delivery


class LifecycleTests(unittest.TestCase):
    def test_inventory_uses_docker_label_filter(self):
        with patch.object(host, 'run', return_value='') as run:
            self.assertEqual(host.inventory(), {'containers': [], 'volumes': [], 'networks': []})
        for call in run.call_args_list:
            self.assertEqual(call.args[-2:], ('--filter', 'label=com.docker.compose.project=${artifactId}'))

    def test_full_deployment_waits_for_all_middleware(self):
        deployment = self.deployment()
        deployment.deploy()
        calls = [call.args for call in deployment.compose.call_args_list]
        self.assertIn(('up', '-d', '--wait', '--wait-timeout', '360', *server.INFRASTRUCTURE), calls)
        self.assertLess(next(i for i,c in enumerate(calls) if c[0] == 'up'), calls.index(('stop', 'nginx', 'app')))

    def test_generated_component_credentials_are_distinct_and_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'backend'
            with patch.object(server, 'WEB_ROOT', Path(tmp) / 'web'):
                server.initialize(root, 80, '0.0.0.0')
            values = dict(line.split('=', 1) for line in (root / '.env').read_text().splitlines())
            self.assertEqual(set(values), server.KEYS)
            self.assertEqual(len({values[key] for key in server.SECRET_KEYS}), len(server.SECRET_KEYS))
            self.assertGreaterEqual(len(server.base64.b64decode(values['NACOS_AUTH_TOKEN'])), 32)

    def test_health_check_rejects_unhealthy_middleware(self):
        deployment = self.deployment()
        deployment.compose.return_value = 'container-id'
        payload = json.dumps([{'State': {'Health': {'Status': 'unhealthy'}}}])
        with patch.object(server.subprocess, 'check_output', return_value=payload):
            with self.assertRaisesRegex(ValueError, 'unhealthy'):
                deployment.verify_infrastructure()

    def test_backend_and_frontend_directory_markers_are_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'backend'
            web = Path(tmp) / 'frontend'
            with patch.object(host, 'WEB_ROOT', web):
                host.ownership(root, create=True)
                host.web_ownership(create=True)
                host.ownership(root)
                host.web_ownership()
                self.assertEqual((root / host.MARKER).read_text().strip(), host.PROJECT)
                self.assertEqual((web / host.MARKER).read_text().strip(), host.PROJECT)
                (root / host.MARKER).write_text('unrelated')
                with self.assertRaisesRegex(ValueError, 'Invalid managed'):
                    host.ownership(root)
                host.web_ownership()

    def deployment(self):
        deployment = object.__new__(server.Deployment)
        deployment.env = {'APP_RELEASE_ID': 'old-app', 'WEB_RELEASE_ID': 'old-web'}
        deployment.manifest = {'release_id': 'new-release'}
        deployment.validate_mode = Mock()
        deployment.record_attempt = Mock()
        deployment.compose = Mock()
        deployment.verify = Mock()
        deployment.commit_release = Mock()
        deployment.publish_frontend = Mock()
        deployment.backup = Mock()
        deployment.sql = Mock(return_value='3')
        return deployment

    def test_frontend_updates_only_nginx_and_keeps_app_version(self):
        deployment = self.deployment()
        deployment.deploy_frontend()
        self.assertEqual(deployment.env['APP_RELEASE_ID'], 'old-app')
        self.assertEqual(deployment.env['WEB_RELEASE_ID'], 'new-release')
        calls = [call.args for call in deployment.compose.call_args_list]
        self.assertIn(('build', '--pull', 'nginx'), calls)
        self.assertFalse(any('app' in call or 'mysql' in call for call in calls))
        deployment.backup.assert_not_called()
        deployment.commit_release.assert_called_once()

    def test_backend_reloads_nginx_without_recreating_it(self):
        deployment = self.deployment()
        deployment.deploy_backend()
        self.assertEqual(deployment.env['WEB_RELEASE_ID'], 'old-web')
        self.assertEqual(deployment.env['APP_RELEASE_ID'], 'new-release')
        deployment.backup.assert_called_once()
        calls = [call.args for call in deployment.compose.call_args_list]
        self.assertIn(('exec', '-T', 'nginx', 'nginx', '-s', 'reload'), calls)
        self.assertFalse(any(call[0] == 'up' and 'nginx' in call for call in calls))
        deployment.commit_release.assert_called_once()

    def test_backend_backup_failure_prevents_replacement(self):
        deployment = self.deployment()
        deployment.backup.side_effect = RuntimeError('backup failed')
        with self.assertRaises(RuntimeError):
            deployment.deploy_backend()
        self.assertFalse(any('--force-recreate' in call.args for call in deployment.compose.call_args_list))
        deployment.commit_release.assert_not_called()

    def test_health_failure_does_not_commit_version(self):
        deployment = self.deployment()
        deployment.verify.side_effect = ValueError('health failed')
        with self.assertRaises(ValueError):
            deployment.deploy_frontend()
        deployment.commit_release.assert_not_called()

    def test_partial_mode_rejects_unselected_changes(self):
        root = Path('/managed/sample')
        deployment = object.__new__(server.Deployment)
        deployment.root = root
        previous = {'release_id': 'old-release', 'files': {'app.jar': 'old-hash', 'app/docker-compose.yml': 'compose'}, 'migrations': {'V1.sql': 'hash'}}
        deployment.manifest = {'release_id': 'new-release', 'files': {'app.jar': 'changed', 'app/docker-compose.yml': 'compose'}, 'migrations': previous['migrations']}
        deployment.state = {'release': 'old-release', 'status': 'healthy'}
        deployment.verify_runtime = Mock()
        with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'is_symlink', return_value=True), \
                patch.object(Path, 'resolve', return_value=root / 'releases/old-release'), \
                patch.object(server, 'verify_release', return_value=previous):
            with self.assertRaisesRegex(ValueError, 'Unselected'):
                deployment.validate_mode('frontend')
        deployment.verify_runtime.assert_not_called()

    def test_nginx_under_environment_keeps_frontend_iteration_boundary(self):
        root = Path('/managed/sample')
        previous = {'release_id': 'old-release', 'files': {'environment/nginx/conf.d/default.conf': 'old'}, 'migrations': {}}
        for mode in ('frontend', 'backend'):
            with self.subTest(mode=mode):
                deployment = object.__new__(server.Deployment)
                deployment.root = root
                deployment.env = {}
                deployment.state = {'release': 'old-release', 'status': 'healthy'}
                deployment.manifest = {'files': {'environment/nginx/conf.d/default.conf': 'new'}, 'migrations': {}}
                deployment.verify_runtime = Mock()
                with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'is_symlink', return_value=True), \
                        patch.object(Path, 'resolve', return_value=root / 'releases/old-release'), \
                        patch.object(server, 'verify_release', return_value=previous):
                    if mode == 'frontend':
                        deployment.validate_mode(mode)
                        deployment.verify_runtime.assert_called_once()
                    else:
                        with self.assertRaisesRegex(ValueError, 'Unselected'):
                            deployment.validate_mode(mode)

    def test_partial_mode_rejects_incomplete_previous_deployment(self):
        deployment = object.__new__(server.Deployment)
        deployment.root = Path('/managed/sample')
        deployment.state = {'status': 'deploying'}
        with patch.object(Path, 'exists', return_value=True), patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaisesRegex(ValueError, 'healthy'):
                deployment.validate_mode('backend')

    def resources(self, root=Path('/managed/sample')):
        return {'containers': [{'Id': 'sample-container', 'Config': {'Labels': {host.LABEL: host.PROJECT,
                'com.docker.compose.project.working_dir': str(root / 'releases/release-id')}}}],
                'volumes': [{'Name': 'sample-volume', 'Labels': {host.LABEL: host.PROJECT}}],
                'networks': [{'Id': 'sample-network', 'Name': 'sample-network', 'Labels': {host.LABEL: host.PROJECT}, 'Containers': {}}]}

    def test_uninstall_preview_has_no_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'releases').mkdir()
            with patch.object(host, 'locked', return_value=contextlib.nullcontext()), \
                    patch.object(host, 'inventory', return_value=self.resources(root)), patch.object(host, 'run') as run:
                host.uninstall(root, code=True)
                run.assert_not_called()
                self.assertTrue((root / 'releases').exists())

    def test_uninstall_preserves_data_code_and_backups_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'releases').mkdir()
            (root / 'backups').mkdir()
            with patch.object(host, 'locked', return_value=contextlib.nullcontext()), \
                    patch.object(host, 'inventory', return_value=self.resources(root)), patch.object(host, 'run') as run:
                host.uninstall(root, execute=True, confirm=host.PROJECT)
                self.assertEqual([c.args for c in run.call_args_list], [('docker', 'rm', '-f', 'sample-container'), ('docker', 'network', 'rm', 'sample-network')])
                self.assertTrue((root / 'releases').is_dir())
                self.assertTrue((root / 'backups').is_dir())

    def test_uninstall_failure_does_not_delete_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'releases').mkdir()
            with patch.object(host, 'locked', return_value=contextlib.nullcontext()), \
                    patch.object(host, 'inventory', return_value=self.resources(root)), patch.object(host, 'run', side_effect=RuntimeError('docker failed')):
                with self.assertRaises(RuntimeError):
                    host.uninstall(root, code=True, execute=True, confirm=host.PROJECT)
                self.assertTrue((root / 'releases').is_dir())

    def test_foreign_network_members_block_uninstall(self):
        root = Path('/managed/sample').resolve()
        resources = self.resources(root)
        resources['networks'][0]['Containers'] = {'foreign-container': {}}
        with patch.object(host, 'locked', return_value=contextlib.nullcontext()), \
                patch.object(host, 'inventory', return_value=resources), patch.object(host, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'foreign'):
                host.uninstall(root, execute=True, confirm=host.PROJECT)
            run.assert_not_called()

    def test_prune_protects_active_and_mounted_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            releases = root / 'releases'
            releases.mkdir()
            for name in ('app-version', 'web-version', 'pending-version', 'database-version'):
                (releases / name).mkdir()
            (root / 'active.json').write_text(json.dumps({'app': 'app-version', 'web': 'web-version', 'release': 'pending-version'}))
            resources = self.resources(root)
            resources['containers'][0]['Mounts'] = [{'Type': 'bind', 'Source': str(releases / 'database-version/environment/mysql/conf.d/my.cnf')}]
            protected = host.protected_releases(root, resources)
            self.assertTrue({(releases / name).resolve() for name in ('pending-version', 'database-version')}.issubset(protected))
            with patch.object(host, 'locked', return_value=contextlib.nullcontext()), patch.object(host, 'inventory', return_value=resources), \
                    patch.object(delivery, 'verify_release', return_value={'release_id': 'app-version'}):
                with self.assertRaisesRegex(ValueError, 'active'):
                    host.prune(root, ['pending-version'], True, host.PROJECT)

    def test_preflight_never_prints_secret_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = 'DO-NOT-PRINT-THIS-PASSWORD'
            resources = {'containers': [], 'volumes': [], 'networks': []}
            def command(*args):
                return '2.24.0' if args[:3] == ('docker', 'compose', 'version') else ''
            output = io.StringIO()
            with patch.object(server, 'configuration', return_value={'HTTP_PORT': '${httpPort}', 'MYSQL_PASSWORD': secret}), \
                    patch.object(host, 'run', side_effect=command), patch.object(host, 'inventory', return_value=resources), \
                    contextlib.redirect_stdout(output):
                host.preflight(root)
            self.assertNotIn(secret, output.getvalue())


if __name__ == '__main__':
    unittest.main()
