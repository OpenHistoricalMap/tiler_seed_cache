FROM ghcr.io/openhistoricalmap/tiler-server:0.0.1-0.dev.git.1720.h88e0835

# Install necessary system dependencies
RUN apk update && apk add --no-cache \
    proj \
    proj-dev \
    gdal \
    gdal-dev \
    geos \
    geos-dev \
    python3-dev \
    py3-pip \
    build-base

# Ensure PROJ_DIR and PATH are set
ENV PROJ_DIR=/usr
ENV PATH="/usr/share/proj:${PATH}"

# Upgrade pip
RUN python3 -m pip install --upgrade pip

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python setup.py install
CMD ["./exec.sh"]
