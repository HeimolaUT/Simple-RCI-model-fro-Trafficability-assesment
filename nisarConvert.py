from pathlib import Path
import h5py
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS


GRID_PATH = "science/LSAR/SME2/grids/algorithmCandidates/DSG"

LAYERS = [
    "soilMoisture",
    "soilMoistureUncertainty",
    "qualityFlag",
    "waterBodyFraction",
    "vegetationWaterContent",
]


def convert_h5_to_tifs(h5_path, out_dir, dst_crs="EPSG:4326"):
    """
    Convert a single NISAR HDF5 file into GeoTIFFs and reproject them.
    """
    h5_path = Path(h5_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True)

    # -----------------------------
    # Read coordinates
    # -----------------------------
    with h5py.File(h5_path, "r") as f:
        x = f[f"{GRID_PATH}/xCoordinates"][:]
        y = f[f"{GRID_PATH}/yCoordinates"][:]

        dx = x[1] - x[0]
        dy = y[1] - y[0]
        y_is_ascending = dy > 0

        transform = from_bounds(
            west=x.min() - abs(dx)/2,
            south=y.min() - abs(dy)/2,
            east=x.max() + abs(dx)/2,
            north=y.max() + abs(dy)/2,
            width=len(x),
            height=len(y)
        )

        crs = CRS.from_epsg(6933)

        # -----------------------------
        # Write each layer
        # -----------------------------
        for layer in LAYERS:
            path = f"{GRID_PATH}/{layer}"
            if path not in f:
                print(f"[WARN] Missing layer {layer}, skipping")
                continue

            data = f[path][:].astype("float32")
            if y_is_ascending:
                data = data[::-1, :]

            tif_path = out_dir / f"{layer}.tif"
            with rasterio.open(
                tif_path, "w",
                driver="GTiff",
                height=data.shape[0],
                width=data.shape[1],
                count=1,
                dtype="float32",
                crs=crs,
                transform=transform,
                nodata=-9999,
                compress="lzw"
            ) as dst:
                dst.write(data, 1)

            print("Wrote", tif_path)

    # -----------------------------
    # Reproject to dst_crs
    # -----------------------------
    reproj_dir = out_dir / "reproj"
    reproj_dir.mkdir(exist_ok=True)

    for tif in out_dir.glob("*.tif"):
        with rasterio.open(tif) as src:
            transform, width, height = calculate_default_transform(
                src.crs, dst_crs,
                src.width, src.height,
                *src.bounds
            )

            meta = src.meta.copy()
            meta.update({
                "crs": dst_crs,
                "transform": transform,
                "width": width,
                "height": height
            })

            out_path = reproj_dir / f"{tif.stem}_4326.tif"
            with rasterio.open(out_path, "w", **meta) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.nearest
                    )

        print("Reprojected", out_path)


def convert_folder(input_folder, output_folder):
    """
    Convert all .h5 files in a folder.
    """
    input_folder = Path(input_folder)
    for h5 in input_folder.glob("*.h5"):
        print("\n=== Processing", h5.name, "===")
        convert_h5_to_tifs(h5, output_folder)
