"""Tests for road-map semantic cost assignment in the map/waypoint editor."""

import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import main_all  # noqa: E402

_APP = QApplication.instance() or QApplication([])


def _qimage_from_array(arr):
    arr = np.ascontiguousarray(arr.astype(np.uint8))
    height, width = arr.shape
    return QImage(arr.tobytes(), width, height, width,
                  QImage.Format.Format_Grayscale8).copy()


def _labels():
    return {
        '0': {'name': 'unknown', 'global_cost': 0, 'local_cost': 0, 'id': 0},
        '1': {'name': 'wall', 'global_cost': 0, 'local_cost': 0, 'id': 1},
        '2': {'name': 'floor', 'global_cost': 0, 'local_cost': 0, 'id': 2},
        '3': {'name': 'grass', 'global_cost': 100, 'local_cost': 70, 'id': 3},
        '4': {'name': 'tactile paving', 'global_cost': 0, 'local_cost': 50, 'id': 4},
        '5': {'name': 'roadway', 'global_cost': 100, 'local_cost': 100, 'id': 5},
        '6': {'name': 'sidewalk', 'global_cost': 0, 'local_cost': 10, 'id': 6},
    }


class TestOccupancyToCost(unittest.TestCase):
    def test_lethal_and_soft_mapping(self):
        self.assertEqual(main_all.ImageViewer._occ_to_cost(0), 0)
        self.assertEqual(main_all.ImageViewer._occ_to_cost(100), 254)
        self.assertEqual(main_all.ImageViewer._occ_to_cost(200), 254)
        self.assertEqual(main_all.ImageViewer._occ_to_cost(50), 126)
        self.assertTrue(0 < main_all.ImageViewer._occ_to_cost(10) < 126)


class TestSemanticCostGrid(unittest.TestCase):
    def _viewer(self):
        viewer = main_all.ImageViewer()
        # 20x20 base map at 0.5 m/cell (free space = 255).
        viewer.map_image_array = np.full((20, 20), 255, dtype=np.uint8)
        viewer.map_origin = (0.0, 0.0)
        viewer.resolution = 0.5
        # 10x10 road map at 1.0 m/cell.
        index_grid = np.full((10, 10), 4, dtype=np.uint8)
        index_grid[0:5, :] = 3  # image row0 = high y
        viewer.roadmap_index_grid = index_grid
        viewer.roadmap_origin = (0.0, 0.0)
        viewer.roadmap_resolution = 1.0
        viewer.roadmap_labels = _labels()
        viewer.semantic_classes = {
            'grass': {'global_cost': 100, 'local_cost': 70},
            'tactile paving': {'global_cost': 0, 'local_cost': 50},
            'roadway': {'global_cost': 100, 'local_cost': 100},
            'sidewalk': {'global_cost': 0, 'local_cost': 10},
        }
        viewer.semantic_enabled = True
        return viewer

    def test_grass_is_lethal_and_tactile_is_soft(self):
        viewer = self._viewer()
        grid = viewer._build_semantic_cost_grid()
        self.assertEqual(grid.shape, (20, 20))
        self.assertEqual(set(np.unique(grid).tolist()), {126, 254})
        # image top rows = grass -> lethal
        self.assertTrue((grid[:10, :] == 254).all())
        self.assertTrue((grid[10:, :] == 126).all())

    def test_unknown_index_is_not_charged(self):
        viewer = self._viewer()
        viewer.roadmap_index_grid[8:, :] = 9  # not present in labels
        grid = viewer._build_semantic_cost_grid()
        # index rows 8-9 live at the low-y side, i.e. the bottom of the base map
        self.assertTrue((grid[-2:, :] == 0).all())

    def test_planning_combines_with_inflation(self):
        viewer = self._viewer()
        viewer.semantic_combine = 'max'
        plan = viewer._ensure_cost_grid()
        values = set(np.unique(plan).tolist())
        self.assertIn(254, values)   # grass = lethal
        self.assertIn(126, values)   # tactile paving = soft cost
        self.assertTrue(all(value <= 254 for value in values))

    def test_semantic_lethal_cells_inflate_neighbors(self):
        """芝生などの致死セルが障害物として膨張を生むこと。"""
        viewer = self._viewer()
        # 膨張半径を広めにして、境界付近の膨張を観測しやすくする
        viewer.inflation_radius = 1.5
        viewer.inflation_inscribed_radius = 0.5
        plan = viewer._ensure_cost_grid()

        # 致死セル以外（tactile側）にも膨張由来のコストが乗る
        soft_side = plan[10:, :]
        self.assertTrue((soft_side > 126).any())

    def test_manual_cost_edit_feeds_planning(self):
        """手動で塗ったコストマップ(costmap_values)が計画に反映されること。"""
        viewer = self._viewer()
        values = np.zeros((10, 10), dtype=np.uint8)
        values[0:3, :] = 100  # 手動で致死コストを塗る
        viewer.costmap_values = _qimage_from_array(values)
        viewer._costmap_revision += 1

        grid = viewer._build_semantic_cost_grid()

        self.assertTrue((grid[:4, :] == 254).all())

    def test_rebuild_costmap_from_classes_updates_values(self):
        """クラス別コスト表が costmap_values を更新すること。"""
        viewer = self._viewer()
        viewer.costmap_labels = {
            3: {'name': 'grass', 'color': (0, 255, 0), 'cost': 100},
            4: {'name': 'tactile paving', 'color': (255, 255, 0), 'cost': 50},
        }
        viewer._rebuild_costmap_from_classes()

        values = viewer._costmap_values_array()
        self.assertIsNotNone(values)
        self.assertEqual(int(values.max()), 100)

        grid = viewer._build_semantic_cost_grid()
        self.assertEqual(set(np.unique(grid).tolist()), {126, 254})


class TestSemanticCostPanel(unittest.TestCase):
    def test_reserved_classes_are_excluded(self):
        panel = main_all.RightPanel()
        panel.set_semantic_classes(_labels())
        self.assertEqual(
            sorted(panel.semantic_class_rows),
            ['grass', 'roadway', 'sidewalk', 'tactile paving'],
        )

    def test_signal_carries_edited_costs(self):
        panel = main_all.RightPanel()
        panel.set_semantic_classes(_labels())
        received = []
        panel.semantic_cost_changed.connect(lambda *args: received.append(args))
        panel.semantic_enable_cb.setChecked(True)
        panel.semantic_class_rows['tactile paving'][1].setValue(30)
        enabled, classes, opacity, combine = received[-1]
        self.assertTrue(enabled)
        self.assertEqual(classes['tactile paving']['local_cost'], 30)
        self.assertEqual(combine, 'max')

    def test_reset_restores_road_map_defaults(self):
        panel = main_all.RightPanel()
        panel.set_semantic_classes(_labels())
        panel.semantic_class_rows['grass'][1].setValue(5)
        panel.reset_semantic_defaults()
        self.assertEqual(panel.semantic_class_rows['grass'][1].value(), 70)


if __name__ == '__main__':
    unittest.main()
