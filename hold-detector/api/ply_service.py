from __future__ import annotations

from pathlib import Path

import numpy as np
import open3d as o3d


def load_point_cloud(ply_path: Path) -> o3d.geometry.PointCloud:
    """Load a single PLY file into a point cloud."""
    return o3d.io.read_point_cloud(str(ply_path))


def render_point_cloud(
    pcd: o3d.geometry.PointCloud,
    width: int = 1920,
    height: int = 1440,
) -> tuple[np.ndarray, o3d.camera.PinholeCameraParameters]:
    """Render the point cloud to a 2D image using an offscreen Open3D visualizer.

    Returns:
        image_bgr: numpy array (H, W, 3) in BGR order for OpenCV compatibility
        cam_params: pinhole camera parameters used for this render (for back-projection)
    """
    # Auto-detect wall orientation via PCA.
    # The wall normal = eigenvector with smallest variance (depth axis).
    # The wall "up" = eigenvector with largest variance (height axis).
    points = np.asarray(pcd.points)
    wall_centroid = points.mean(axis=0)
    _, eigenvectors = np.linalg.eigh(np.cov((points - wall_centroid).T))
    # eigh returns eigenvalues ascending: [smallest, mid, largest]
    wall_normal = eigenvectors[:, 0]   # least variance = depth/normal
    wall_up = eigenvectors[:, 2]       # most variance = height

    # Ensure the normal points away from the data centroid (camera looks inward)
    # by checking orientation — flip if needed so camera is on the positive side
    if np.dot(wall_normal, wall_centroid) < 0:
        wall_normal = -wall_normal

    vis = o3d.visualization.Visualizer()
    vis.create_window(width=width, height=height, visible=False)
    vis.add_geometry(pcd)

    render_opt = vis.get_render_option()
    render_opt.point_size = 5.0

    ctr = vis.get_view_control()
    ctr.set_front((-wall_normal).tolist())   # camera looks toward the wall
    ctr.set_up((-wall_up).tolist())
    ctr.set_zoom(0.5)

    vis.poll_events()
    vis.update_renderer()

    cam_params = ctr.convert_to_pinhole_camera_parameters()

    # Capture as RGB float image then convert to uint8 BGR
    image_rgb = np.asarray(vis.capture_screen_float_buffer(do_render=True))
    vis.destroy_window()

    image_rgb_u8 = (image_rgb * 255).astype(np.uint8)
    image_bgr = image_rgb_u8[:, :, ::-1].copy()
    return image_bgr, cam_params


def compute_depth(
    bbox_xyxy: tuple[float, float, float, float],
    pcd: o3d.geometry.PointCloud,
    cam_params: o3d.camera.PinholeCameraParameters,
    padding: float = 0.5,
) -> float:
    """Return the protrusion depth of a hold from the local wall surface (metres).

    Projects all PLY points to image space, collects those inside the hold bbox,
    fits a plane to them via PCA, and returns the range along the local normal
    (max - min signed distance). This equals the depth from the wall surface
    behind the hold to its outermost point.

    padding: fraction of bbox size added around the bbox to capture wall context.
    """
    points = np.asarray(pcd.points)
    if len(points) == 0:
        return 0.0

    intrinsic = cam_params.intrinsic
    extrinsic = cam_params.extrinsic

    ones = np.ones((points.shape[0], 1))
    pts_h = np.hstack([points, ones])
    pts_cam = (extrinsic @ pts_h.T).T[:, :3]

    front = pts_cam[:, 2] > 0
    pts_cam = pts_cam[front]
    pts_world = points[front]

    if len(pts_cam) == 0:
        return 0.0

    fx = intrinsic.intrinsic_matrix[0, 0]
    fy = intrinsic.intrinsic_matrix[1, 1]
    cx = intrinsic.intrinsic_matrix[0, 2]
    cy = intrinsic.intrinsic_matrix[1, 2]

    px = fx * (pts_cam[:, 0] / pts_cam[:, 2]) + cx
    py = fy * (pts_cam[:, 1] / pts_cam[:, 2]) + cy

    x1, y1, x2, y2 = bbox_xyxy
    bw, bh = x2 - x1, y2 - y1
    rx1 = x1 - padding * bw
    rx2 = x2 + padding * bw
    ry1 = y1 - padding * bh
    ry2 = y2 + padding * bh

    inside = (px >= rx1) & (px <= rx2) & (py >= ry1) & (py <= ry2)
    region_pts = pts_world[inside]

    if len(region_pts) < 4:
        return 0.0

    centroid = region_pts.mean(axis=0)
    _, eigenvectors = np.linalg.eigh(np.cov((region_pts - centroid).T))
    local_normal = eigenvectors[:, 0]  # smallest variance = surface normal

    signed_dists = (region_pts - centroid) @ local_normal
    return float(signed_dists.max() - signed_dists.min())


def pixel_to_3d(
    u: float,
    v: float,
    pcd: o3d.geometry.PointCloud,
    cam_params: o3d.camera.PinholeCameraParameters,
    search_radius: float = 5.0,
) -> np.ndarray | None:
    """Unproject pixel (u, v) back to 3D world coordinates.

    Projects all point cloud points through the camera intrinsics/extrinsics,
    finds the nearest projected point to (u, v), and returns its 3D world position.
    Returns None if no point is found within search_radius pixels.
    """
    intrinsic = cam_params.intrinsic
    extrinsic = cam_params.extrinsic  # 4x4 world-to-camera

    points = np.asarray(pcd.points)
    if len(points) == 0:
        return None

    ones = np.ones((points.shape[0], 1))
    pts_h = np.hstack([points, ones])  # (N, 4)
    pts_cam = (extrinsic @ pts_h.T).T[:, :3]  # (N, 3)

    mask = pts_cam[:, 2] > 0
    pts_cam = pts_cam[mask]
    pts_world = points[mask]

    if len(pts_cam) == 0:
        return None

    fx = intrinsic.intrinsic_matrix[0, 0]
    fy = intrinsic.intrinsic_matrix[1, 1]
    cx = intrinsic.intrinsic_matrix[0, 2]
    cy = intrinsic.intrinsic_matrix[1, 2]

    px = fx * (pts_cam[:, 0] / pts_cam[:, 2]) + cx
    py = fy * (pts_cam[:, 1] / pts_cam[:, 2]) + cy

    dists = (px - u) ** 2 + (py - v) ** 2
    idx = int(np.argmin(dists))

    if dists[idx] > search_radius ** 2:
        return None

    return pts_world[idx]
