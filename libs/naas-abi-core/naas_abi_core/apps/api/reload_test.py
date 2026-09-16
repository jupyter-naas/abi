"""The API must watch editable sources in both ABI repository layouts."""
import importlib.util
import tempfile
import threading
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('reload_paths', Path(__file__).with_name('reload.py'))
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReloadDirectoryTests(unittest.TestCase):
    def test_normal_layout_and_missing_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'src').mkdir()
            (root / 'libs').mkdir()
            self.assertEqual(module.reload_directories(root), [str((root / 'src').resolve()), str((root / 'libs').resolve())])

    def test_submodule_layout_explicitly_watches_real_sources(self):
        from uvicorn.config import Config
        from uvicorn.supervisors.watchfilesreload import FileFilter
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / '.abi/libs/package/app'
            target.mkdir(parents=True)
            (root / 'src').mkdir()
            (root / 'libs').mkdir()
            (root / 'libs/package').symlink_to(target.parent)
            paths = module.reload_directories(root)
            changed = (target / 'ontology_dictionary.py').resolve()
            config = Config('example:app', reload=True, reload_dirs=paths)
            self.assertIn((root / '.abi/libs').resolve(), config.reload_dirs)
            self.assertTrue(FileFilter(config)(changed))

    def test_native_watcher_observes_an_edit_inside_hidden_submodule(self):
        from watchfiles import watch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / '.abi/libs/package/app'
            target.mkdir(parents=True)
            (root / 'libs').mkdir()
            (root / 'libs/package').symlink_to(target.parent)
            changed = target / 'ontology_dictionary.py'
            changed.write_text('VERSION = 1\n')
            stopped = threading.Event()
            def edit():
                if not stopped.wait(0.3):
                    changed.write_text('VERSION = 2\n')
            thread = threading.Thread(target=edit)
            thread.start()
            try:
                events = next(watch(*module.reload_directories(root), watch_filter=None, stop_event=stopped, yield_on_timeout=True, rust_timeout=2500, debounce=50, step=20))
                self.assertTrue(any(Path(path).resolve() == changed.resolve() for _, path in events))
            finally:
                stopped.set()
                thread.join()

if __name__ == '__main__':
    unittest.main()
