# -*- coding: utf-8 -*-
"""Batch CHM-based plot height extraction for UAV/low-altitude LiDAR data.

Pipeline
--------
LAS/LAZ -> plot clipping by Shapefile -> class 2/1 split ->
gridded DEM P05 / DSM P99 -> CHM = DSM - DEM -> P100/P99.5/P99 -> CSV.

The scientific defaults are kept from the supplied research script. Paths and
runtime options are exposed through a command-line interface so the project can
be cloned and run on another machine without editing source code.
"""

import argparse
import os
import re
import sys
import time

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, box
from shapely.prepared import prep

try:
    import laspy
except ImportError:  # Allow ``--help`` and parser tests without optional I/O dependency.
    laspy = None


DEFAULT_CELL_M = 0.10
DEFAULT_DTM_PCT = 5.0
DEFAULT_DSM_PCT = 99.0
DEFAULT_BORDER_RATIO = 0.20
DEFAULT_PCTS_IN_PLOT = (100.0, 99.5, 99.0)
DEFAULT_BATCH_SIZE = 10_000_000


def _require_laspy():
    if laspy is None:
        raise RuntimeError(
            "laspy is required for LAS/LAZ processing. Install dependencies from "
            "requirements.txt or environment.yml."
        )


def _copy_scale_offset(source_header, target_header):
    """Copy coordinate scale/offset across laspy versions."""
    if hasattr(source_header, "scales") and hasattr(target_header, "scales"):
        target_header.scales = source_header.scales
    elif hasattr(source_header, "scale") and hasattr(target_header, "scale"):
        target_header.scale = source_header.scale

    if hasattr(source_header, "offsets") and hasattr(target_header, "offsets"):
        target_header.offsets = source_header.offsets
    elif hasattr(source_header, "offset") and hasattr(target_header, "offset"):
        target_header.offset = source_header.offset


def grid_percentile(x, y, z, cell=DEFAULT_CELL_M, q=99.0, xlim=None, ylim=None):
    """Aggregate Z values into a regular XY grid using a per-cell percentile."""
    if len(x) == 0:
        return (0.0, 0.0), np.array([]), np.array([]), np.full((0, 0), np.nan)

    if xlim is None:
        xmin, xmax = float(np.min(x)), float(np.max(x))
    else:
        xmin, xmax = xlim
    if ylim is None:
        ymin, ymax = float(np.min(y)), float(np.max(y))
    else:
        ymin, ymax = ylim

    xmin = np.floor(xmin / cell) * cell
    ymin = np.floor(ymin / cell) * cell
    xmax = np.ceil(xmax / cell) * cell
    ymax = np.ceil(ymax / cell) * cell

    nx = int(round((xmax - xmin) / cell)) + 1
    ny = int(round((ymax - ymin) / cell)) + 1

    ix = np.clip(((x - xmin) / cell).astype(int), 0, nx - 1)
    iy = np.clip(((y - ymin) / cell).astype(int), 0, ny - 1)

    frame = pd.DataFrame({"iy": iy, "ix": ix, "z": z})
    aggregated = frame.groupby(["iy", "ix"])["z"].quantile(q / 100.0)

    grid = np.full((ny, nx), np.nan, float)
    indices = aggregated.index.to_frame(index=False)
    grid[indices["iy"].values, indices["ix"].values] = aggregated.values

    x_centers = xmin + np.arange(nx) * cell
    y_centers = ymin + np.arange(ny) * cell
    return (xmin, ymin), x_centers, y_centers, grid


def divide(input_las_file, shapefile_path, id_field="Id", batch_size=DEFAULT_BATCH_SIZE):
    """Clip one LAS/LAZ file into plot-level LAS files defined by a Shapefile."""
    _require_laspy()
    gdf = gpd.read_file(shapefile_path)
    if id_field not in gdf.columns:
        raise ValueError(
            "Shapefile ID field {!r} was not found. Available fields: {}".format(
                id_field, ", ".join(map(str, gdf.columns))
            )
        )

    las = laspy.read(input_las_file)
    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_las_file)), "region")
    os.makedirs(output_dir, exist_ok=True)

    total_points = len(las.x)
    start_index = 0
    region_data = {
        region[id_field]: {
            "points": [],
            "colors": [],
            "intensities": [],
            "classification": [],
            "polygon": region.geometry,
        }
        for _, region in gdf.iterrows()
    }

    while start_index < total_points:
        end_index = min(start_index + batch_size, total_points)
        batch_x = las.x[start_index:end_index]
        batch_y = las.y[start_index:end_index]
        batch_z = las.z[start_index:end_index]

        batch_red = (
            las.red[start_index:end_index]
            if hasattr(las, "red")
            else np.zeros_like(batch_x)
        )
        batch_green = (
            las.green[start_index:end_index]
            if hasattr(las, "green")
            else np.zeros_like(batch_x)
        )
        batch_blue = (
            las.blue[start_index:end_index]
            if hasattr(las, "blue")
            else np.zeros_like(batch_x)
        )
        batch_intensity = (
            las.intensity[start_index:end_index]
            if hasattr(las, "intensity")
            else np.zeros_like(batch_x)
        )
        # Important: classification must be sliced with the same batch bounds.
        batch_classification = las.classification[start_index:end_index]

        batch_points = np.vstack([batch_x, batch_y, batch_z]).T
        batch_colors = np.vstack([batch_red, batch_green, batch_blue]).T

        for region_id, data in region_data.items():
            polygon = data["polygon"]
            minx, miny, maxx, maxy = polygon.bounds
            bbox_mask = (
                (batch_points[:, 0] >= minx)
                & (batch_points[:, 0] <= maxx)
                & (batch_points[:, 1] >= miny)
                & (batch_points[:, 1] <= maxy)
            )

            candidate_points = batch_points[bbox_mask]
            if len(candidate_points) == 0:
                continue

            candidate_colors = batch_colors[bbox_mask]
            candidate_intensities = batch_intensity[bbox_mask]
            candidate_classification = batch_classification[bbox_mask]

            final_mask = np.array(
                [polygon.contains(Point(point[0], point[1])) for point in candidate_points],
                dtype=bool,
            )
            filtered_points = candidate_points[final_mask]
            if len(filtered_points) == 0:
                continue

            data["points"].append(filtered_points)
            data["colors"].append(candidate_colors[final_mask])
            data["intensities"].append(candidate_intensities[final_mask])
            data["classification"].append(candidate_classification[final_mask])

        start_index = end_index

    for region_id, data in region_data.items():
        if not data["points"]:
            continue

        all_points = np.vstack(data["points"])
        all_colors = np.vstack(data["colors"])
        all_intensities = np.concatenate(data["intensities"])
        all_classification = np.concatenate(data["classification"])

        header = laspy.LasHeader(
            point_format=las.header.point_format, version=las.header.version
        )
        _copy_scale_offset(las.header, header)
        new_las = laspy.LasData(header)
        new_las.x = all_points[:, 0]
        new_las.y = all_points[:, 1]
        new_las.z = all_points[:, 2]

        if hasattr(new_las, "red"):
            new_las.red = all_colors[:, 0]
        if hasattr(new_las, "green"):
            new_las.green = all_colors[:, 1]
        if hasattr(new_las, "blue"):
            new_las.blue = all_colors[:, 2]
        if hasattr(new_las, "intensity"):
            new_las.intensity = all_intensities
        new_las.classification = all_classification

        output_file = os.path.join(output_dir, "{}_output.las".format(region_id))
        new_las.write(output_file)

    return output_dir


def classification(file_path):
    """Split plot LAS into class 2 (ground) and class 1 (non-ground/vegetation)."""
    _require_laspy()
    las = laspy.read(file_path)
    point_classification = np.asarray(las.classification)
    available = set(int(value) for value in np.unique(point_classification))

    missing = [cls for cls in (1, 2) if cls not in available]
    if missing:
        missing_text = ", ".join("class {}".format(cls) for cls in missing)
        raise ValueError(
            "{} is missing required {}. Available classes: {}".format(
                os.path.basename(file_path),
                missing_text,
                ", ".join(map(str, sorted(available))) or "none",
            )
        )

    input_folder = os.path.dirname(file_path)
    output_folder = os.path.join(input_folder, "classification")
    os.makedirs(output_folder, exist_ok=True)
    output_paths = {}

    for cls in (1, 2):
        mask = point_classification == cls
        las_class = laspy.create(
            point_format=las.header.point_format,
            file_version=las.header.version,
        )
        las_class.points = las.points[mask]
        _copy_scale_offset(las.header, las_class.header)
        base_name = os.path.splitext(os.path.basename(file_path))[0].split("_")[0]
        output_path = os.path.join(output_folder, "{}_class_{}.las".format(base_name, cls))
        las_class.write(output_path)
        output_paths[cls] = output_path

    ground_las = laspy.read(output_paths[2])
    non_ground_las = laspy.read(output_paths[1])
    return ground_las, non_ground_las


def grid_chm_heights(
    vegetation_las,
    ground_las,
    cell=DEFAULT_CELL_M,
    dtm_pct=DEFAULT_DTM_PCT,
    dsm_pct=DEFAULT_DSM_PCT,
    border_ratio=DEFAULT_BORDER_RATIO,
    pcts=DEFAULT_PCTS_IN_PLOT,
):
    """Compute plot CHM percentile heights from vegetation and ground points."""
    gx, gy, gz = ground_las.x, ground_las.y, ground_las.z
    vx, vy, vz = vegetation_las.x, vegetation_las.y, vegetation_las.z
    if len(gx) == 0 or len(vx) == 0:
        return {
            "H_CHM_P{}".format(str(p).replace(".", "_")): np.nan for p in pcts
        }

    min_x = max(gx.min(), vx.min())
    max_x = min(gx.max(), vx.max())
    min_y = max(gy.min(), vy.min())
    max_y = min(gy.max(), vy.max())
    if min_x >= max_x or min_y >= max_y:
        return {
            "H_CHM_P{}".format(str(p).replace(".", "_")): np.nan for p in pcts
        }

    new_min_x = float(min_x + (max_x - min_x) * border_ratio)
    new_max_x = float(max_x - (max_x - min_x) * border_ratio)
    new_min_y = float(min_y + (max_y - min_y) * border_ratio)
    new_max_y = float(max_y - (max_y - min_y) * border_ratio)

    ground_mask = (
        (gx >= new_min_x)
        & (gx <= new_max_x)
        & (gy >= new_min_y)
        & (gy <= new_max_y)
    )
    vegetation_mask = (
        (vx >= new_min_x)
        & (vx <= new_max_x)
        & (vy >= new_min_y)
        & (vy <= new_max_y)
    )
    gx, gy, gz = gx[ground_mask], gy[ground_mask], gz[ground_mask]
    vx, vy, vz = vx[vegetation_mask], vy[vegetation_mask], vz[vegetation_mask]
    if len(gx) < 10 or len(vx) < 10:
        return {
            "H_CHM_P{}".format(str(p).replace(".", "_")): np.nan for p in pcts
        }

    xlim = (float(min(gx.min(), vx.min())), float(max(gx.max(), vx.max())))
    ylim = (float(min(gy.min(), vy.min())), float(max(gy.max(), vy.max())))

    _, x_centers, y_centers, dem = grid_percentile(
        gx, gy, gz, cell=cell, q=dtm_pct, xlim=xlim, ylim=ylim
    )
    _, _, _, dsm = grid_percentile(
        vx, vy, vz, cell=cell, q=dsm_pct, xlim=xlim, ylim=ylim
    )
    if dem.size == 0 or dsm.size == 0:
        return {
            "H_CHM_P{}".format(str(p).replace(".", "_")): np.nan for p in pcts
        }

    chm = dsm - dem
    xx, yy = np.meshgrid(x_centers, y_centers)
    centers = np.column_stack([xx.ravel(), yy.ravel()])
    inner_polygon = box(new_min_x, new_min_y, new_max_x, new_max_y)
    prepared_polygon = prep(inner_polygon)
    inside = np.array(
        [prepared_polygon.contains(Point(px, py)) for px, py in centers], dtype=bool
    )
    values = chm.ravel()[inside]
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return {
            "H_CHM_P{}".format(str(p).replace(".", "_")): np.nan for p in pcts
        }

    output = {}
    for percentile in pcts:
        key = "H_CHM_P{}".format(str(percentile).replace(".", "_"))
        output[key] = float(np.nanpercentile(values, percentile))
    return output


def file_paths_in_dir(folder, recursive=False):
    """Return LAS/LAZ paths in a directory, optionally recursively."""
    if not recursive:
        return sorted(
            os.path.join(folder, name)
            for name in os.listdir(folder)
            if name.lower().endswith((".las", ".laz"))
        )

    paths = []
    for root, _, files in os.walk(folder):
        for name in files:
            if name.lower().endswith((".las", ".laz")):
                paths.append(os.path.join(root, name))
    return sorted(paths)


def decode_model_from_filename(name):
    """Decode the project's optional seven-digit H/V/O/A filename convention."""
    match = re.search(r"(\d{7})", name)
    model = match.group(1) if match else None
    height = speed = overlap = angle = None
    if model:
        height = int(model[:2])
        speed_map = {"2": 2.0, "3": 3.9, "4": 3.9, "8": 8.0}
        speed = speed_map.get(model[2])
        overlap = int(model[3:5])
        angle = -int(model[5:7])
    return model, height, speed, overlap, angle


def build_parser():
    parser = argparse.ArgumentParser(
        description="Batch plot-level crop height extraction from UAV LiDAR LAS/LAZ data."
    )
    parser.add_argument("--input", required=True, help="LAS/LAZ file or directory containing LAS/LAZ files")
    parser.add_argument("--shp", required=True, help="Plot boundary Shapefile (.shp)")
    parser.add_argument("--output", required=True, help="Output summary CSV path")
    parser.add_argument("--id-field", default="Id", help="Plot ID field in the Shapefile (default: Id)")
    parser.add_argument("--cell", type=float, default=DEFAULT_CELL_M, help="Grid cell size in metres (default: 0.10)")
    parser.add_argument("--dtm-pct", type=float, default=DEFAULT_DTM_PCT, help="Ground DEM percentile (default: 5)")
    parser.add_argument("--dsm-pct", type=float, default=DEFAULT_DSM_PCT, help="Canopy DSM percentile (default: 99)")
    parser.add_argument("--border-ratio", type=float, default=DEFAULT_BORDER_RATIO, help="Plot border shrink ratio (default: 0.20)")
    parser.add_argument("--recursive", action="store_true", help="Recursively search for LAS/LAZ files")
    return parser


def _validate_args(args):
    if not os.path.exists(args.input):
        return "Input path does not exist: {}".format(args.input)
    if os.path.isfile(args.input) and not args.input.lower().endswith((".las", ".laz")):
        return "Input file must be LAS/LAZ: {}".format(args.input)
    if not os.path.isfile(args.shp):
        return "Shapefile does not exist: {}".format(args.shp)
    if not args.shp.lower().endswith(".shp"):
        return "Shapefile path must end with .shp: {}".format(args.shp)
    if args.cell <= 0:
        return "--cell must be greater than 0"
    if not (0 <= args.dtm_pct <= 100 and 0 <= args.dsm_pct <= 100):
        return "--dtm-pct and --dsm-pct must be between 0 and 100"
    if not (0 <= args.border_ratio < 0.5):
        return "--border-ratio must be at least 0 and less than 0.5"
    return None


def run_pipeline(args):
    _require_laspy()
    output_parent = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(output_parent, exist_ok=True)

    if os.path.isfile(args.input):
        las_files = [os.path.abspath(args.input)]
    else:
        las_files = file_paths_in_dir(args.input, recursive=args.recursive)
    if not las_files:
        raise ValueError("No LAS/LAZ files found in input path: {}".format(args.input))

    rows = []
    for index, las_path in enumerate(las_files, 1):
        print("[{}/{}] {}".format(index, len(las_files), os.path.basename(las_path)))
        region_dir = divide(las_path, args.shp, id_field=args.id_field)
        region_files = sorted(
            os.path.join(region_dir, name)
            for name in os.listdir(region_dir)
            if name.lower().endswith("_output.las")
        )

        if not region_files:
            print("  - no plot points intersected the Shapefile", file=sys.stderr)
            continue

        for region_file in region_files:
            try:
                ground_las, vegetation_las = classification(region_file)
                heights = grid_chm_heights(
                    vegetation_las,
                    ground_las,
                    cell=args.cell,
                    dtm_pct=args.dtm_pct,
                    dsm_pct=args.dsm_pct,
                    border_ratio=args.border_ratio,
                    pcts=DEFAULT_PCTS_IN_PLOT,
                )
                row = {
                    "filename": os.path.basename(las_path),
                    "region_file": os.path.basename(region_file),
                    "plot_id": os.path.splitext(os.path.basename(region_file))[0].split("_")[0],
                    "cell_m": args.cell,
                    "dtm_pct": args.dtm_pct,
                    "dsm_pct": args.dsm_pct,
                    "border_ratio": args.border_ratio,
                }
                row.update(heights)
                model, height, speed, overlap, angle = decode_model_from_filename(
                    os.path.basename(las_path)
                )
                row.update({"Model": model, "H": height, "V": speed, "O": overlap, "A": angle})
                rows.append(row)
            except Exception as exc:
                print(
                    "  - region failed: {}: {}".format(os.path.basename(region_file), exc),
                    file=sys.stderr,
                )

    if not rows:
        raise ValueError("No plot-height results were produced.")

    result = pd.DataFrame(rows)
    for column in [name for name in result.columns if name.startswith("H_CHM_P")]:
        result[column] = result[column] * 100.0  # metres -> centimetres
    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    print("Saved: {} ({} rows)".format(args.output, len(result)))
    return len(result)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validation_error = _validate_args(args)
    if validation_error:
        print("Error: {}".format(validation_error), file=sys.stderr)
        return 2

    started = time.time()
    try:
        run_pipeline(args)
    except Exception as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1
    print("Done in {:.1f}s".format(time.time() - started))
    return 0


if __name__ == "__main__":
    sys.exit(main())
