from __future__ import annotations

import cv2
import numpy as np


def clamp_box(box: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    x1 = max(0, min(width - 1, int(np.floor(x1))))
    y1 = max(0, min(height - 1, int(np.floor(y1))))
    x2 = max(x1 + 1, min(width, int(np.ceil(x2))))
    y2 = max(y1 + 1, min(height, int(np.ceil(y2))))
    return x1, y1, x2, y2


def mask_centroid(mask: np.ndarray, box: list[float]) -> tuple[int, int]:
    moments = cv2.moments(mask.astype(np.uint8))
    if moments["m00"]:
        return int(moments["m10"] / moments["m00"]), int(moments["m01"] / moments["m00"])
    x1, y1, x2, y2 = box
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def contour_metrics(mask: np.ndarray) -> tuple[int, float]:
    contours, _ = cv2.findContours(
        (mask.astype(np.uint8) * 255),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        return 999, 0.0
    contour = max(contours, key=cv2.contourArea)
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return 999, 0.0
    approx = cv2.approxPolyDP(contour, 0.03 * perimeter, True)
    (_, _), (rect_w, rect_h), _ = cv2.minAreaRect(contour)
    rect_area = max(float(rect_w * rect_h), 1.0)
    return len(approx), float(cv2.contourArea(contour)) / rect_area


def intersection_over_smaller_box(box_a: list[float], box_b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    area_a = max(1.0, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1.0, (bx2 - bx1) * (by2 - by1))
    return inter / min(area_a, area_b)


def intersection_over_smaller_mask(
    mask_a: np.ndarray,
    mask_b: np.ndarray,
    box_a: list[float],
    box_b: list[float],
    image_shape: tuple[int, int],
) -> float:
    height, width = image_shape
    ax1, ay1, ax2, ay2 = clamp_box(box_a, width, height)
    bx1, by1, bx2, by2 = clamp_box(box_b, width, height)
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix1 >= ix2 or iy1 >= iy2:
        return 0.0
    crop_a = mask_a[iy1:iy2, ix1:ix2]
    crop_b = mask_b[iy1:iy2, ix1:ix2]
    inter = int(np.logical_and(crop_a, crop_b).sum())
    area_a = max(1, int(mask_a.sum()))
    area_b = max(1, int(mask_b.sum()))
    return inter / min(area_a, area_b)
