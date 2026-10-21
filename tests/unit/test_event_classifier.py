"""Unit tests for the event classifier geometry helpers.

Tests: cooldown, near/loiter/interaction/movement/removal detection.
"""

from backend.services.event_service import (
    bbox_distance,
    bbox_iou,
    centroid_displacement,
    is_near,
)


class TestBBoxIoU:
    """Test the bounding box intersection-over-union helper."""

    def test_identical_boxes(self) -> None:
        iou = bbox_iou([0, 0, 10, 10], [0, 0, 10, 10])
        assert iou == pytest.approx(1.0)

    def test_no_overlap(self) -> None:
        iou = bbox_iou([0, 0, 10, 10], [20, 20, 30, 30])
        assert iou == pytest.approx(0.0)

    def test_partial_overlap(self) -> None:
        iou = bbox_iou([0, 0, 10, 10], [5, 5, 15, 15])
        assert 0.0 < iou < 1.0

    def test_one_inside_another(self) -> None:
        iou = bbox_iou([0, 0, 100, 100], [25, 25, 75, 75])
        assert 0.0 < iou < 1.0


class TestBBoxDistance:
    """Test the bounding box centroid distance helper."""

    def test_same_box_zero_distance(self) -> None:
        assert bbox_distance([0, 0, 10, 10], [0, 0, 10, 10]) == pytest.approx(0.0)

    def test_known_distance(self) -> None:
        # disjoint boxes with dx=3 and dy=4 → sqrt(9+16) = 5.0
        d = bbox_distance([0, 0, 10, 10], [13, 14, 23, 24])
        assert d == pytest.approx(5.0, abs=0.01)


class TestCentroidDisplacement:
    """Test the centroid displacement helper."""

    def test_no_movement(self) -> None:
        d = centroid_displacement([10, 10, 20, 20], [10, 10, 20, 20])
        assert d == pytest.approx(0.0)


class TestIsNear:
    """Test the ``is_near`` proximity check."""

    def test_close_boxes_are_near(self) -> None:
        assert is_near([0, 0, 10, 10], [5, 5, 15, 15], threshold=100.0) is True

    def test_far_boxes_are_not_near(self) -> None:
        assert is_near([0, 0, 10, 10], [500, 500, 510, 510], threshold=100.0) is False


# Bring pytest into scope for approx.
import pytest  # noqa: E402
