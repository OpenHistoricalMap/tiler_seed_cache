import click
import asyncio
from tiler_benchmark.utils import (
    geojson_to_tiles,
    measure_tile_response_times_by_zoom,
    upload_to_s3,
)


@click.command(short_help="Script to request tiles from a Tiler API.")
@click.option(
    "--geojson-url",
    required=True,
    default="https://gist.githubusercontent.com/Rub21/5bc8ecf4d828dcae52e5512680c02d00/raw/83cd86dd8330ee84c29e7028000a8a955329f0c5/ds.geojson",
)
@click.option(
    "--zoom-levels",
    help="Comma-separated list of zoom levels",
    default="8,9,10",
)
@click.option(
    "--output-file",
    help="Output CSV file name",
    default="dc_tile_response_times.csv",
)
@click.option(
    "--s3-bucket",
    help="S3 bucket to upload the result CSV file",
    default="osmseed-dev",
)
def main(geojson_url, zoom_levels, output_file, s3_bucket):
    """Main function to fetch tiles and measure response times."""
    zoom_levels = list(map(int, zoom_levels.split(",")))
    tile_data = geojson_to_tiles(geojson_url, zoom_levels)
    asyncio.run(measure_tile_response_times_by_zoom(tile_data, zoom_levels, output_file))
    if s3_bucket:
        upload_to_s3(output_file, s3_bucket)


if __name__ == "__main__":
    main()
