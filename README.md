
# Tiler Benchmark

This repository checks carefully how much time each tile request takes to respond. It also generates and requests tiles, so that future requests should take significantly less time to respond.


## Build and test

```sh
docker-compose build
docker-compose run tiler_benchmark bash
```

- Run Example

```sh

python main.py --country-code="USA" --province-code="US-CA" --zoom-levels 5,6,7,8,9,10,11,12,13,14,15

```