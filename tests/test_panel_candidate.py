import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('candidate', Path(__file__).parents[1] / 'tools/build_panel_candidate.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class CandidateTests(unittest.TestCase):
    def test_unrecognized_input_fails_before_any_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'context_token_injector.py').write_text('raise RuntimeError("must never execute")')
            with self.assertRaises(ValueError):
                candidate.build(root)

    def test_unknown_or_duplicated_boundaries_are_rejected(self):
        for source in ('no markers', 'begin one end begin two end'):
            with self.assertRaises(ValueError):
                candidate.cut(source, 'begin', 'end')
