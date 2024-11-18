
# Titler Cache Seed

This repository aims to generate cache files for the tiler, using polygons or points geojson files as input. The script calculates the tiles and then passes them to Tegola’s seed to generate the cache files, in order to imporve the performance of the tiler server.


## Build and test

```sh
docker-compose build
docker-compose run tiler_benchmark bash
```
