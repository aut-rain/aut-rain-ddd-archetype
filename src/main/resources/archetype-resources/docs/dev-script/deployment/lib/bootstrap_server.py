#set( $dollar = '$' )
#set( $hash = '#' )
"""Verify and safely install one uploaded release without starting containers."""
import argparse
import os
import re
import sys
import tarfile
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from delivery import digest, relative_file, verify_release


def install(package, root):
    if not root.is_absolute() or root != root.resolve() or len(root.parts) < 3:
        raise ValueError('Use a canonical absolute application directory')
    package = package.resolve(strict=True)
    sidecar = Path(str(package) + '.sha256')
    expected = sidecar.read_text(encoding='ascii').split()
    if len(expected) < 1 or expected[0] != digest(package):
        raise ValueError('Package checksum verification failed')
    releases = root / 'releases'
    if releases.is_symlink():
        raise ValueError('Releases directory cannot be a symlink')
    releases.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.incoming-', dir=releases) as temporary:
        with tarfile.open(package, 'r:gz') as archive:
            members = archive.getmembers()
            roots = set()
            names = set()
            for member in members:
                if member.name in names:
                    raise ValueError('Duplicate archive entry')
                names.add(member.name)
                path = relative_file(member.name)
                roots.add(path.parts[0])
                if not (member.isfile() or member.isdir()):
                    raise ValueError('Release archive contains a link or special file')
            if len(roots) != 1:
                raise ValueError('Release archive must contain one top-level directory')
            release_id = roots.pop()
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,80}', release_id):
                raise ValueError('Invalid release identifier')
            archive.extractall(temporary, members=members)
        stage = Path(temporary) / release_id
        manifest = verify_release(stage)
        if manifest['release_id'] != release_id:
            raise ValueError('Release directory and manifest do not match')
        final = releases / release_id
        if final.exists() or final.is_symlink():
            raise FileExistsError('Release already exists; deployments are immutable: ' + str(final))
        os.rename(stage, final)
    print('Verified and installed ' + release_id + ' at ' + str(releases / release_id))
    print('No services were started or changed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['extract'])
    parser.add_argument('--root', type=Path, default=Path('/opt/${artifactId}'))
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Run release installation on the Linux server')
    root = args.root
    if not root.is_absolute() or root != root.resolve() or len(root.parts) < 3:
        parser.error('--root must be an absolute application directory')
    install(args.package, root)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, tarfile.TarError) as error:
        print('Release installation failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
