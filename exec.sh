#!/bin/bash
set -x

# Set environment variables with default values if not already set
: "${GEOJSON_URL:="https://gist.githubusercontent.com/Rub21/9aaf349d74d974c0393700af8eeeb43d/raw/9f8fa0dde911705208141a4ff941e2e5b51e245b/eu.geojson"}"
: "${ZOOM_LEVELS:="5,6,7,8,9}"
: "${OUTPUT_FILE:="eu_tile_response_times.csv"}"
: "${S3_BUCKET:="osmseed-dev"}"

# Run the benchmark
tiler_benchmark \
  --geojson-url "$GEOJSON_URL" \
  --zoom-levels "$ZOOM_LEVELS" \
  --output-file "$OUTPUT_FILE" \
  --s3-bucket "$S3_BUCKET"