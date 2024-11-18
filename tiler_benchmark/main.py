import click
import asyncio
from utils import (
    upload_to_s3,
    seed_tiles,
    save_geojson_boundary,
    read_geojson_boundary,
    boundary_to_tiles
)
@click.command(short_help="Script to request or seed tiles from a Tiler API.")
@click.option(
    "--geojson-url",
    required=True,
    help="URL to the GeoJSON file defining the area of interest.",
)
@click.option(
    "--feature-type",
    required=True,
    help="type of objects in the geojson file",
    default="polygon",
)
@click.option(
    "--zoom-levels",
    help="Comma-separated list of zoom levels",
    default="8,9,10",
)
@click.option(
    "--concurrency",
    help="Number of concurrent processes for seeding",
    default=32,
    type=int,
)
@click.option(
    "--s3-bucket",
    help="S3 bucket to upload the result CSV file",
    default="osmseed-dev",
)
@click.option(
    "--log-file",
    help="CSV file to save the logs results",
    default="log_file.csv",
)

def main(geojson_url, feature_type, zoom_levels, concurrency, log_file, s3_bucket):
    """
    Main function to process and seed tiles, with results uploaded to S3.
    """
    zoom_levels = list(map(int, zoom_levels.split(",")))
    min_zoom = min(zoom_levels)
    max_zoom = max(zoom_levels)
    print(f"Min Zoom: {min_zoom}, Max Zoom: {max_zoom}")

    # Read boundary geometry from GeoJSON
    boundary_geometry = read_geojson_boundary(geojson_url, feature_type)
    if not boundary_geometry:
        print("No valid boundary geometry found.")
        return

    # Save the boundary geometry to a GeoJSON file for verification
    geojson_file = f"boundaries_{log_file}.geojson"

    save_geojson_boundary(boundary_geometry, geojson_file)
    upload_to_s3(geojson_file, s3_bucket, f"tiler/logs/{geojson_file}")

    # Generate tiles based on boundary geometry and zoom levels
    tiles = boundary_to_tiles(boundary_geometry, zoom_levels)

    skipped_tiles_file = f"skipped_tiles_{log_file}"
    # Seed the tiles
    seed_tiles(
        tiles, concurrency, min_zoom, max_zoom, log_file, skipped_tiles_file
    )

    print("Tile seeding complete.")
    print(f"Skipped tiles saved to: {skipped_tiles_file}")
    print(f"Log of seeding performance saved to: {log_file}")

    # Upload log files to S3
    upload_to_s3(log_file, s3_bucket, f"tiler/logs/{log_file}")
    upload_to_s3(skipped_tiles_file, s3_bucket, f"tiler/logs/{skipped_tiles_file}")
    print("Log files saved to S3.")

if __name__ == "__main__":
    main()
    