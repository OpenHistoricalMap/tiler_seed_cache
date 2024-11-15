import requests
import geopandas as gpd
import mercantile
from shapely.geometry import shape
import aiohttp
import time
import os
import csv
from tqdm import tqdm
import asyncio
import boto3
from botocore.exceptions import NoCredentialsError
import requests
import geopandas as gpd
import mercantile
from shapely.geometry import shape, MultiPolygon


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
    response = requests.get(geojson_url)
    response.raise_for_status()
    geojson_data = response.json()

    gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])

    if gdf.empty:
        print("No geometry found in GeoJSON.")
        return []

    geometry = gdf.unary_union
    result = []

    for zoom in zoom_levels:
        minx, miny, maxx, maxy = geometry.bounds
        for tile in mercantile.tiles(minx, miny, maxx, maxy, zoom):
            tile_geom = shape(mercantile.feature(tile)["geometry"])
            if geometry.intersects(tile_geom):
                centroid_lon, centroid_lat = tile_to_centroid(tile.x, tile.y, tile.z)
                result.append(
                    {
                        "url": base_url.format(z=tile.z, x=tile.x, y=tile.y),
                        "centroid": (centroid_lon, centroid_lat),
                        "zoom": zoom,  # Explicitly store the zoom level
                    }
                )

    return result


async def fetch_tile(session, url, timeout=600):
    start_time = time.time()
    try:
        # Wrap the coroutine `session.get(url)` in `asyncio.wait_for`
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
    # Open the file in write mode initially to create the file and write the header
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

        # Append results for this zoom level to the existing CSV file
        with open(output_file, mode="a", newline="") as file:
            writer = csv.writer(file)

            for tile, result in zip(zoom_tile_data, results):
                url = tile["url"]
                lon, lat = tile["centroid"]
                _, response_time = result

                # Write to CSV
                writer.writerow(
                    [url, lon, lat, response_time if response_time is not None else "failed", zoom]
                )

                # Log results
                if response_time is not None:
                    print(f"Tile {url} (Centroid: {lon}, {lat}) took {response_time:.2f} seconds")
                else:
                    print(f"Tile {url} (Centroid: {lon}, {lat}) failed to fetch.")

    print(f"\nAll results saved to {output_file}")


def upload_to_s3(file_path, s3_bucket):
    s3 = boto3.client("s3")
    s3_key = os.path.basename(file_path)

    try:
        s3.upload_file(file_path, s3_bucket, s3_key)
        print(f"File uploaded to s3://{s3_bucket}/tiler_benchmark/{s3_key}")
    except FileNotFoundError:
        print(f"File {file_path} not found.")
    except NoCredentialsError:
        print("Credentials not available for S3 upload.")
