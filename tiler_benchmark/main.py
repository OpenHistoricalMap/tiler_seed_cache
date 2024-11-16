import click
import asyncio
from tiler_benchmark.utils import (
    geojson_to_tiles,
    measure_tile_response_times_by_zoom,
    upload_to_s3,
    seed_tiles
)
@click.command(short_help="Script to request or seed tiles from a Tiler API.")
@click.option(
    "--geojson-url",
    required=True,
    help="URL to the GeoJSON file defining the area of interest.",
)
@click.option(
    "--zoom-levels",
    help="Comma-separated list of zoom levels",
    default="8,9,10",
)
@click.option(
    "--output-file",
    help="Output CSV file name for response times",
    default="dc_tile_response_times.csv",
)
@click.option(
    "--s3-bucket",
    help="S3 bucket to upload the result CSV file",
    default="osmseed-dev",
)
@click.option(
    "--type",
    help="Operation type: seed or request",
    default="seed",
)
@click.option(
    "--concurrency",
    help="Number of concurrent processes for seeding",
    default=32,
    type=int,
)
def main(geojson_url, zoom_levels, output_file, s3_bucket, type, concurrency):
    zoom_levels = list(map(int, zoom_levels.split(",")))
    tile_data = geojson_to_tiles(geojson_url, zoom_levels)

    if type == "seed":
        print("Starting seeding process...")
        seed_tiles(tile_data, concurrency)
    else:
        print("Measuring tile response times...")
        asyncio.run(measure_tile_response_times_by_zoom(tile_data, zoom_levels, output_file))
        if s3_bucket:
            print(f"Uploading {output_file} to S3 bucket {s3_bucket}...")
            upload_to_s3(output_file, s3_bucket)


if __name__ == "__main__":
    main()