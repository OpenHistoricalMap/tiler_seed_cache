#!/bin/bash
set -x

# tiler_benchmark
# Set environment variables with default values if not already set
: "${GEOJSON_URL:="https://osmseed-dev.s3.amazonaws.com/tiler/population_500000_us.geojson"}"
: "${ZOOM_LEVELS:="11,12,13,14,16"}"
: "${OUTPUT_FILE:="population_500000_us.csv"}"
: "${S3_BUCKET:="osmseed-dev"}"
: "${FEATURE_TYPE:="Point"}"
: "${CONCURRENCY:="64"}"

# Run the benchmark
tiler_benchmark \
  --geojson-url "$GEOJSON_URL" \
  --feature-type "$FEATURE_TYPE" \
  --zoom-levels "$ZOOM_LEVELS" \
  --concurrency "$CONCURRENCY" \
  --s3-bucket "$S3_BUCKET" \
  --log-file "$OUTPUT_FILE"
