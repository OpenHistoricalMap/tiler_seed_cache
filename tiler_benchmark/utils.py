import requests
import mercantile
from shapely.geometry import shape
from shapely.ops import unary_union 
import aiohttp
import time
import csv
import os
from tqdm import tqdm
import boto3
from botocore.exceptions import NoCredentialsError
import subprocess
import asyncio


def tile_to_centroid(x, y, z):
    bounds = mercantile.bounds(x, y, z)
    centroid_lon = (bounds.west + bounds.east) / 2
    centroid_lat = (bounds.south + bounds.north) / 2

    return centroid_lon, centroid_lat

def geojson_to_tiles(
    geojson_url,
    zoom_levels,
    base_url="https://vtiles.openhistoricalmap.org/maps/osm/{z}/{x}/{y}.pbf",
):
    # Fetch GeoJSON data
    response = requests.get(geojson_url)
    response.raise_for_status()
    geojson_data = response.json()

    # Extract geometries from GeoJSON features
    geometries = [shape(feature["geometry"]) for feature in geojson_data["features"]]

    if not geometries:
        print("No geometry found in GeoJSON.")
        return []

    # Create a unified geometry (unary union)
    geometry = unary_union(geometries)

    result = []

    for zoom in zoom_levels:
        # Get the bounds of the unified geometry
        minx, miny, maxx, maxy = geometry.bounds
        # Iterate over tiles that intersect the bounding box
        for tile in mercantile.tiles(minx, miny, maxx, maxy, zoom):
            # Check if the tile geometry intersects the unified geometry
            tile_geom = shape(mercantile.feature(tile)["geometry"])
            if geometry.intersects(tile_geom):
                # Compute the centroid of the tile
                centroid_lon, centroid_lat = tile_to_centroid(tile.x, tile.y, tile.z)
                result.append(
                    {
                        "url": base_url.format(z=tile.z, x=tile.x, y=tile.y),
                        "centroid": (centroid_lon, centroid_lat),
                        "zoom": zoom, 
                        "z": tile.z,
                        "x": tile.x,
                        "y": tile.y
                    }
                )

    return result


def seed_tiles(tile_data, concurrency):
    """
    Seeds tiles using Tegola, skipping previously failed tiles.
    """
    SKIPPED_TILES_FILE = "skipped_tiles.log"

    def load_skipped_tiles():
        """Load previously skipped tiles from the log file."""
        if os.path.exists(SKIPPED_TILES_FILE):
            with open(SKIPPED_TILES_FILE, "r") as file:
                return set(line.strip() for line in file)
        return set()

    def save_skipped_tile(tile):
        """Save a skipped tile to the log file."""
        with open(SKIPPED_TILES_FILE, "a") as file:
            file.write(f"{tile}\n")

    skipped_tiles = load_skipped_tiles()
    failed_tiles = []

    for tile in tile_data:
        z, x, y = tile["z"], tile["x"], tile["y"]
        tile_string = f"{z}/{x}/{y}"

        # Skip previously logged skipped tiles
        if tile_string in skipped_tiles:
            print(f"Skipping previously skipped tile: {tile_string}")
            continue

        try:
            print(f"Seeding tile: {tile_string} with concurrency {concurrency}")
            result = subprocess.run(
                [
                    "tegola", "cache", "seed",
                    "tile-list", "-",
                    "--config=/opt/tegola_config/config.toml",
                    "--map=osm",
                    "--min-zoom", str(z),
                    "--max-zoom", str(z),  # Limit to the specific zoom level
                    f"--concurrency={concurrency}",
                ],
                input=f"{tile_string}\n".encode(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if result.returncode != 0:
                print(f"Failed to seed tile: {tile_string}")
                failed_tiles.append(tile_string)
                save_skipped_tile(tile_string)  # Save failed tile for next run
            else:
                print(f"Successfully seeded tile: {tile_string}")

        except Exception as e:
            print(f"Error processing tile {tile_string}: {e}")
            save_skipped_tile(tile_string)  # Save tile that caused an exception

    print("Seeding process complete.")
    if failed_tiles:
        print(f"Failed tiles: {failed_tiles}")

async def fetch_tile(session, url, timeout=600):
    start_time = time.time()
    try:
        response = await asyncio.wait_for(session.get(url), timeout=timeout)
        response_time = time.time() - start_time
        await response.read()  # Read response to complete the request
        response.raise_for_status()
        return url, response_time
    except asyncio.TimeoutError:
        print(f"Timeout: Tile {url} took longer than {timeout} seconds to respond.")
        return url, None
    except Exception as e:
        print(f"Failed to fetch tile {url}: {e}")
        return url, None


async def measure_tile_response_times_by_zoom(tile_data, zoom_levels, output_file):
    with open(output_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["URL", "lon", "lat", "response_time", "zoom"])

    for zoom in zoom_levels:
        print(f"\nProcessing tiles for zoom level {zoom}...")
        zoom_tile_data = [tile for tile in tile_data if tile["zoom"] == zoom]

        if not zoom_tile_data:
            print(f"No tiles found for zoom level {zoom}.")
            continue

        async with aiohttp.ClientSession() as session:
            tasks = [fetch_tile(session, tile["url"]) for tile in zoom_tile_data]
            results = [await t for t in tqdm(asyncio.as_completed(tasks), total=len(tasks))]

        with open(output_file, mode="a", newline="") as file:
            writer = csv.writer(file)

            for tile, result in zip(zoom_tile_data, results):
                url = tile["url"]
                lon, lat = tile["centroid"]
                _, response_time = result

                writer.writerow(
                    [url, lon, lat, response_time if response_time is not None else "failed", zoom]
                )

                if response_time is not None:
                    print(f"Tile {url} (Centroid: {lon}, {lat}) took {response_time:.2f} seconds")
                else:
                    print(f"Tile {url} (Centroid: {lon}, {lat}) failed to fetch.")

    print(f"\nAll results saved to {output_file}")


def upload_to_s3(file_path, s3_bucket):
    s3 = boto3.client("s3")
    s3_key = os.path.basename(file_path)
    s3_key = f"tiler_benchmark/{s3_key}"
    try:
        s3.upload_file(file_path, s3_bucket, s3_key)
        print(f"File uploaded to s3://{s3_bucket}/{s3_key}")
    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except NoCredentialsError:
        print("Credentials not available for S3 upload.")
