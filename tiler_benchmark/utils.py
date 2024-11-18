import requests
import mercantile
from shapely.geometry import shape, Point, mapping
from shapely.ops import unary_union
import csv
import os
import subprocess
import tempfile
import json
from smart_open import open as s3_open


def read_geojson_boundary(geojson_url, feature_type, buffer_distance_km=0.01):
    response = requests.get(geojson_url)
    response.raise_for_status()
    geojson_data = response.json()

    # Extract geometries from GeoJSON features
    geometries = [shape(feature["geometry"]) for feature in geojson_data["features"]]

    if not geometries:
        print("No geometry found in GeoJSON.")
        return None

    if feature_type == "Polygon":
        return unary_union(geometries)
    elif feature_type == "Point":
        buffered_geometries = [geom.buffer(buffer_distance_km) for geom in geometries if isinstance(geom, Point)]
        return unary_union(buffered_geometries) if buffered_geometries else None
    else:
        raise ValueError(f"Unsupported feature type: {feature_type}. Supported types are 'polygon' and 'point'.")


def save_geojson_boundary(boundary_geometry, file_path):
    if boundary_geometry is None:
        print("No geometry to save.")
        return

    try:
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": mapping(boundary_geometry),
                    "properties": {}
                }
            ]
        }

        # Save to file
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(geojson_data, file, ensure_ascii=False, indent=4)
        print(f"GeoJSON saved successfully to {file_path}")
    except Exception as e:
        print(f"Error saving GeoJSON file: {e}")


def boundary_to_tiles(boundary_geometry, zoom_levels):
    if boundary_geometry is None:
        print("No valid geometry provided.")
        return []
    result = []

    for zoom in zoom_levels:
        minx, miny, maxx, maxy = boundary_geometry.bounds
        for tile in mercantile.tiles(minx, miny, maxx, maxy, zoom):
            tile_geom = shape(mercantile.feature(tile)["geometry"])
            if boundary_geometry.intersects(tile_geom):
                result.append(
                    {
                        "z": tile.z,
                        "x": tile.x,
                        "y": tile.y
                    }
                )

    return result


def seed_tiles(tile_data, concurrency, min_zoom, max_zoom, log_file, skipped_tiles_file):
    """
    Seeds tiles using Tegola, skipping previously failed tiles, with verbose logging.
    Saves logs containing "took" (tile path and time) to a specified CSV file.
    Skips previously failed tiles and updates the skipped tiles file with new failures.
    """
    def load_skipped_tiles():
        """Load previously skipped tiles from the file, or start fresh if the file doesn't exist."""
        if os.path.exists(skipped_tiles_file):
            with open(skipped_tiles_file, "r") as file:
                return set(line.strip() for line in file)
        return set()

    def save_skipped_tiles(skipped_tiles):
        """Overwrite the skipped tiles file with the new set of skipped tiles."""
        with open(skipped_tiles_file, "w") as file:
            for tile in skipped_tiles:
                file.write(f"{tile}\n")

    def save_took_log_csv(log_data):
        """Save logs containing 'took' (tile path and time) to a CSV file."""
        with open(log_file, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(log_data)

    # Initialize CSV file with headers
    with open(log_file, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Tile", "Time"])

    skipped_tiles = load_skipped_tiles()
    failed_tiles = []

    for tile in tile_data:
        z, x, y = tile["z"], tile["x"], tile["y"]
        tile_string = f"{z}/{x}/{y}"

        # Skip previously logged skipped tiles
        if tile_string in skipped_tiles:
            print(f"Skipping previously skipped tile: {tile_string}")
            continue

        # Create a temporary file to hold the tile list
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_tile_file:
            temp_tile_file.write(f"{tile_string}\n")
            temp_tile_file_path = temp_tile_file.name

        try:
            print(f"Seeding tile: {tile_string} with concurrency {concurrency}")
            # Execute the seeding using a bash command in verbose mode
            command = f"""
            tegola cache seed tile-list {temp_tile_file_path} \
                --config=/opt/tegola_config/config.toml \
                --map=osm \
                --min-zoom={min_zoom} \
                --max-zoom={max_zoom} \
                --concurrency={concurrency}
            """
            print(f"Executing command:\n{command}")
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            for line in process.stdout:
                print(f"STDOUT: {line.strip()}")
                if "took" in line:
                    # Extract the tile path and time
                    parts = line.strip().split()
                    tile_path = parts[8].strip("()")  # Extract "13/2408/3077"
                    time_info = parts[-1]            # Extract "10201ms"
                    print(f"Extracted log: {tile_path} {time_info}")
                    save_took_log_csv([tile_path, time_info])

            for line in process.stderr:
                print(f"STDERR: {line.strip()}")

            process.wait()

            if process.returncode != 0:
                print(f"Failed to seed tile: {tile_string}")
                failed_tiles.append(tile_string)
            else:
                print(f"Successfully seeded tile: {tile_string}")

        except Exception as e:
            print(f"Error processing tile {tile_string}: {e}")
            failed_tiles.append(tile_string)

        finally:
            try:
                os.remove(temp_tile_file_path)
            except Exception as cleanup_error:
                print(f"Failed to remove temporary file: {cleanup_error}")

    # Update skipped tiles file with the new failures
    save_skipped_tiles(set(failed_tiles))
    print("Seeding process complete.")
    if failed_tiles:
        print(f"Failed tiles: {failed_tiles}")
    return failed_tiles

def upload_to_s3(local_file, s3_bucket, s3_key):
    s3_url = f"s3://{s3_bucket}/{s3_key}"
    print(f"Uploading {local_file} to {s3_url}...")
    with open(local_file, "rb") as local:
        with s3_open(s3_url, "wb") as remote:
            remote.write(local.read())
    print(f"Uploaded {local_file} to {s3_url}.")