import time
import utils
import trimesh
import matplotlib.pyplot as plt
import circle_fit
import pandas as pd
import shapely
import numpy as np


def head_direction(polygon, hc_maj_axis_pts):
    """finds which pt of the head central axis corresponds to the aritcular surface
    and returns the row the point is in the array
    """
    bound = polygon.minimum_rotated_rectangle
    mnr = utils.minor_axis(bound)
    mnr_line = shapely.geometry.LineString(mnr)

    # split it
    half_slices = shapely.ops.split(polygon, mnr_line)
    half_poly_residual = []
    for half_poly in half_slices.geoms:
        pts = np.asarray(half_poly.exterior.xy).T
        _, _, _, residual = circle_fit.least_squares_circle(pts)
        half_poly_residual.append(residual)
    articular_half_centroid = np.asarray(
        half_slices.geoms[np.argmin(half_poly_residual)].centroid
    )

    hc_axis_pt0_dist = np.abs(
        utils._dist(articular_half_centroid, hc_maj_axis_pts[0, :])
    )
    hc_axis_pt1_dist = np.abs(
        utils._dist(articular_half_centroid, hc_maj_axis_pts[1, :])
    )

    if hc_axis_pt0_dist < hc_axis_pt1_dist:
        return 0
    else:
        return 1


def multislice(mesh, num_slice):
    # get length of the tranformed bone
    total_length = np.sum(abs(mesh.bounds[:, -1]))  # entire length of bone
    neg_length = mesh.bounds[
        mesh.bounds[:, -1] <= 0, -1
    ]  # bone in negative space, bone past the centerline midpoint

    distal_cutoff = 0.85 * total_length + neg_length
    proximal_cutoff = 0.99 * total_length + neg_length

    # spacing of cuts
    cuts = np.linspace(distal_cutoff, proximal_cutoff, num=num_slice)

    for cut in cuts:
        try:
            path = mesh.section(plane_origin=[0, 0, cut], plane_normal=[0, 0, 1])
            slice, to_3d = path.to_planar()
        except:
            break

        # get shapely object from path
        polygon = slice.polygons_closed[0]

        yield [polygon, to_3d]


def axis(mesh, transform, slice_num=20):
    t0 = time.time()
    # copy mesh then make changes
    mesh_rot = mesh.copy()
    mesh_rot.apply_transform(transform)

    # find maximmum major axis
    max_length = None
    for slice in multislice(mesh_rot, slice_num):
        polygon, to_3d = slice
        length = utils.major_axis_dist(polygon.minimum_rotated_rectangle)
        if max_length is None or length > max_length:
            max_length = length
            max_poly = polygon
            max_to_3d = to_3d

    max_angle = utils.azimuth(max_poly.minimum_rotated_rectangle)

    # find axes points
    maj_axis_pts = utils.major_axis(max_poly.minimum_rotated_rectangle)
    min_axis_pts = utils.minor_axis(max_poly.minimum_rotated_rectangle)

    # find location in array of the pt  that corrresponds to the articular portion
    dir = head_direction(max_poly, maj_axis_pts)

    # add in column of zeros
    maj_axis_pts = utils.z_zero_col(maj_axis_pts)
    min_axis_pts = utils.z_zero_col(min_axis_pts)

    # transform to 3d
    maj_axis_pts = utils.transform_pts(maj_axis_pts, max_to_3d)
    min_axis_pts = utils.transform_pts(min_axis_pts, max_to_3d)

    # transform back
    maj_axis_pts_ct = utils.transform_pts(maj_axis_pts, utils.inv_transform(transform))
    min_axis_pts_ct = utils.transform_pts(min_axis_pts, utils.inv_transform(transform))

    # pull out id'd articular pt
    articular_pt = maj_axis_pts_ct[dir, :].reshape(1, 3)

    # version should be the smaller of the two anlges the line makes
    version = max_angle
    if version > 90:
        version = 180 - version

    # version is being measure from y-axis, switch to x-axis
    version = 90 - version

    return maj_axis_pts_ct, min_axis_pts_ct, version, articular_pt
