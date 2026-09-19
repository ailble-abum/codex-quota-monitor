"""Companion sizing uses logical window dimensions, independently of panel size."""
import unittest

from context_token_injector import INJECTION_SCRIPT
from test_context_token_inspector import block, run_js


class CompanionScaleTests(unittest.TestCase):
    def test_auto_size_preserves_small_windows_and_caps_large_windows(self):
        self.assertIn('function companionScale', INJECTION_SCRIPT)
        source = block('function companionScale', 'function mascotScale')
        self.assertEqual(run_js(source, "[companionScale(null,1280,800),companionScale('auto',1440,900),companionScale('auto',1920,1080),companionScale('auto',3840,2160),companionScale('auto',3000,800)]"), [1, 1, 1.2, 1.5, 1])

    def test_manual_size_is_independent_of_window_and_bad_values_use_auto(self):
        self.assertIn('function companionScale', INJECTION_SCRIPT)
        source = block('function companionScale', 'function mascotScale')
        self.assertEqual(run_js(source, "[companionScale('1.5',800,600),companionScale('0.75',3840,2160),companionScale('2',1280,800),companionScale('broken',1920,1080),companionScale('',1920,1080),companionScale('Infinity',1920,1080),companionScale('0',1920,1080),companionScale('9',1920,1080)]"), [1.5, .75, 2, 1.2, 1.2, 1.2, 1.2, 1.2])

    def test_double_size_companion_stays_inside_bottom_during_drag(self):
        source = block('function dockVerticalY', 'function ensureMascot')
        self.assertEqual(run_js(source, "[dockVerticalY(900,800,40,96),mascotDragGeometry({pointerY:200,top:180},900,800,40,96).y,dockVerticalY(-10,800,40,96)]"), [696, 696, 64])


if __name__ == '__main__':
    unittest.main()
