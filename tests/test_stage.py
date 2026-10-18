"""Staging must not overwrite active or unrelated work."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.stage_octabam import plan, retired_paths, validate_target


class StageGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.run_git('init', '-b', 'main', str(self.repo))
        self.run_git('-C', str(self.repo), '-c', 'user.name=Test',
                     '-c', 'user.email=test@example.invalid',
                     'commit', '--allow-empty', '-m', 'baseline')
        self.commit = self.run_git('-C', str(self.repo), 'rev-parse', 'HEAD').strip()
        self.work = self.root / 'work'
        self.run_git('-C', str(self.repo), 'worktree', 'add', '--detach', str(self.work))

    def run_git(self, *args):
        return subprocess.check_output(['git', *args], text=True, stderr=subprocess.DEVNULL)

    def test_clean_isolated_worktree_passes(self):
        validate_target(self.work, self.commit)

    def test_primary_wrong_revision_and_dirty_targets_fail(self):
        with self.assertRaisesRegex(ValueError, 'primary'):
            validate_target(self.repo, self.commit)
        with self.assertRaisesRegex(ValueError, 'HEAD'):
            validate_target(self.work, '0' * 40)
        (self.work / 'active.txt').write_text('unfinished work')
        with self.assertRaisesRegex(ValueError, 'local changes'):
            validate_target(self.work, self.commit)

    def test_source_staging_plan_and_symlink_escape(self):
        source = self.root / 'source'
        name = 'modules/example/code.s'
        src = source / name
        src.parent.mkdir(parents=True)
        src.write_text('; source')
        receipt = {'files': {name: {'path': name}}, 'submodules': {}}
        self.assertEqual(plan(source, self.work, receipt), [(src.resolve(), self.work.resolve() / name)])
        (self.work / 'modules').symlink_to(source / 'modules', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            plan(source, self.work, receipt)

    def test_historical_shared_helpers_do_not_overwrite_builder_source(self):
        source = self.root / 'source'
        name = 'modules/example/code.s'
        src = source / name
        src.parent.mkdir(parents=True)
        src.write_text('; current author source')
        shared = 'tools/verify/verify_dram_boot.py'
        destination = self.work / shared
        destination.parent.mkdir(parents=True)
        destination.write_text('# current builder gate')
        receipt = {'files': {name: {'path': name},
                             shared: {'path': shared, 'stage': False}}, 'submodules': {}}
        self.assertEqual(plan(source, self.work, receipt),
                         [(src.resolve(), self.work.resolve() / name)])
        self.assertEqual(destination.read_text(), '# current builder gate')

    def test_rename_preserves_origin_and_retires_only_tracked_files(self):
        source = self.root / 'source'
        old, new = 'modules/old/manifest.py', 'modules/new/manifest.py'
        src, dst = source / new, self.work / old
        src.parent.mkdir(parents=True)
        dst.parent.mkdir(parents=True)
        src.write_text('# new name')
        dst.write_text('# original')
        self.run_git('-C', str(self.work), 'add', old)
        receipt = {'files': {new: {'path': old}}, 'submodules': {}}
        self.assertEqual(plan(source, self.work, receipt), [(src.resolve(), self.work.resolve() / new)])
        self.assertEqual(retired_paths(self.work, receipt), [dst.resolve()])
        receipt['files'][new]['path'] = 'modules/untracked.py'
        (self.work / 'modules/untracked.py').write_text('active work')
        with self.assertRaisesRegex(ValueError, 'not tracked'):
            retired_paths(self.work, receipt)
        receipt['files'][new]['path'] = 'modules/../../outside.py'
        with self.assertRaisesRegex(ValueError, 'Invalid original'):
            retired_paths(self.work, receipt)

    def test_recorded_removal_and_absent_original(self):
        old = 'modules/example/obsolete.s'
        path = self.work / old
        path.parent.mkdir(parents=True)
        path.write_text('; original')
        self.run_git('-C', str(self.work), 'add', old)
        receipt = {'files': {}, 'retired_files': {old: {'path': old}}}
        self.assertEqual(retired_paths(self.work, receipt), [path.resolve()])
        receipt['retired_files']['modules/example/never-staged.s'] = {}
        self.assertEqual(retired_paths(self.work, receipt), [path.resolve()])
        receipt['files'][old] = {'path': old}
        with self.assertRaisesRegex(ValueError, 'Invalid original'):
            retired_paths(self.work, receipt)

    def test_removal_rejects_untracked_and_symlink_targets(self):
        old = 'modules/example/obsolete.s'
        path = self.work / old
        path.parent.mkdir(parents=True)
        path.write_text('; user work')
        receipt = {'files': {}, 'retired_files': {old: {}}}
        with self.assertRaisesRegex(ValueError, 'not tracked'):
            retired_paths(self.work, receipt)
        path.unlink()
        path.symlink_to(self.root / 'outside.s')
        with self.assertRaisesRegex(ValueError, 'Invalid original'):
            retired_paths(self.work, receipt)


if __name__ == '__main__':
    unittest.main()
