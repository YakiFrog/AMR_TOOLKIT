"""Tests for the built-in Sirius waypoint format."""

import unittest

import main_all
from src.core.models import Waypoint as ModularWaypoint
from src.ui.main_window import MainWindow as ModularMainWindow
from src.utils.format_manager import (
    WAYPOINT_ATTRIBUTE_DEFAULTS as MODULAR_DEFAULTS,
    WAYPOINT_FORMAT as MODULAR_FORMAT,
    count_configured_waypoint_actions as count_modular_actions,
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
    'manual',
]


class _ValueConverter:
    """Provide the conversion method used by the export helper."""

    convert_value = main_all.MainWindow.convert_value


class _ModularValueConverter:
    """Provide the modular conversion method used by its export helper."""

    convert_value = ModularMainWindow.convert_value


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

    def test_export_omits_unconfigured_actions(self):
        """Omit every action parameter when it retains its default value."""
        waypoint = main_all.Waypoint(10, 20)
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

        for key in EXPECTED_DEFAULTS:
            self.assertIsNone(values[key])

        modular_waypoint = ModularWaypoint(10, 20)
        modular_converter = _ModularValueConverter()
        for key, default in MODULAR_DEFAULTS.items():
            self.assertIsNone(
                ModularMainWindow.get_waypoint_value(
                    modular_converter,
                    modular_waypoint,
                    key,
                    MODULAR_FORMAT['format'][key],
                ),
                msg=f'{key}={default!r} should be omitted',
            )

    def test_export_includes_only_configured_actions(self):
        """Export action parameters only when their values are configured."""
        waypoint = main_all.Waypoint(10, 20)
        waypoint.attributes['stop'] = 'True'
        waypoint.attributes['wait_time'] = '2.5'
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

        self.assertTrue(values['stop'])
        self.assertEqual(values['wait_time'], 2.5)
        for key in set(EXPECTED_DEFAULTS) - {'stop', 'wait_time'}:
            self.assertIsNone(values[key])

    def test_default_actions_do_not_produce_a_badge(self):
        """Hide the map badge when every action retains its default value."""
        defaults_as_text = {
            key: str(value) for key, value in EXPECTED_DEFAULTS.items()
        }

        self.assertEqual(
            main_all.count_configured_waypoint_actions(EXPECTED_DEFAULTS), 0
        )
        self.assertEqual(
            main_all.count_configured_waypoint_actions(defaults_as_text), 0
        )
        self.assertEqual(count_modular_actions(EXPECTED_DEFAULTS), 0)
        self.assertEqual(count_modular_actions(defaults_as_text), 0)

    def test_badge_counts_only_configured_actions(self):
        """Show the badge count for values that differ from their defaults."""
        actions = dict(EXPECTED_DEFAULTS)
        actions['stop'] = True
        actions['wait_time'] = '2.5'

        self.assertEqual(
            main_all.count_configured_waypoint_actions(actions), 2
        )
        self.assertEqual(count_modular_actions(actions), 2)


if __name__ == '__main__':
    unittest.main()
