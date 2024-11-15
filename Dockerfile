FROM python:3.10
RUN apt-get update
RUN python -m pip install --upgrade pip
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade --ignore-installed --no-cache-dir -r requirements.txt
COPY . .
RUN python setup.py install
RUN tiler_benchmark --help
CMD [ "./exec.sh" ]
