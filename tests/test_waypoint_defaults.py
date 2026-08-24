"""Tests for the built-in Sirius waypoint format."""

import unittest

import main_all
from src.core.models import Waypoint as ModularWaypoint
from src.utils.format_manager import (
    WAYPOINT_ATTRIBUTE_DEFAULTS as MODULAR_DEFAULTS,
    WAYPOINT_FORMAT as MODULAR_FORMAT,
)


EXPECTED_DEFAULTS = {
    'rotate': 0.0,
    'stop': False,
    'wait_time': 0.0,
    'change_map': '',
    'threshold': -1.0,
    'person_area': False,
}

EXPECTED_FIELDS = [
    'number',
    'x',
    'y',
    'angle_radians',
    'rotate',
    'stop',
    'wait_time',
    'change_map',
    'threshold',
    'person_area',
]


class _ValueConverter:
    """Provide the conversion method used by the export helper."""

    convert_value = main_all.MainWindow.convert_value


class TestWaypointDefaults(unittest.TestCase):
    """Verify both application entry points use the same defaults."""

    def setUp(self):
        """Reset counters so waypoint numbers remain deterministic."""
        main_all.Waypoint.reset_counter()
        ModularWaypoint.reset_counter()

    def test_main_application_waypoint_has_all_defaults(self):
        """Initialize every Sirius attribute in the desktop application."""
        waypoint = main_all.Waypoint(10, 20)

        self.assertEqual(waypoint.attributes, EXPECTED_DEFAULTS)
        self.assertEqual(
            list(main_all.WAYPOINT_FORMAT['format']), EXPECTED_FIELDS
        )

    def test_modular_application_uses_identical_defaults(self):
        """Keep the modular application format aligned with main_all."""
        waypoint = ModularWaypoint(10, 20)

        self.assertEqual(waypoint.attributes, EXPECTED_DEFAULTS)
        self.assertEqual(dict(MODULAR_DEFAULTS), EXPECTED_DEFAULTS)
        self.assertEqual(list(MODULAR_FORMAT['format']), EXPECTED_FIELDS)

    def test_export_includes_empty_change_map_default(self):
        """Preserve change_map even when its default value is empty."""
        waypoint = main_all.Waypoint(10, 20)
        waypoint.attributes = {}
        converter = _ValueConverter()

        values = {
            key: main_all.MainWindow.get_waypoint_value(
                converter,
                waypoint,
                key,
                main_all.WAYPOINT_FORMAT['format'][key],
            )
            for key in EXPECTED_FIELDS
        }

        self.assertEqual(values['change_map'], '')
        self.assertEqual(values['rotate'], 0.0)
        self.assertEqual(values['threshold'], -1.0)
        self.assertFalse(values['person_area'])


if __name__ == '__main__':
    unittest.main()
