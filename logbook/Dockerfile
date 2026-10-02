FROM ghcr.io/home-assistant/base-python:3.13-alpine3.23

WORKDIR /app

# Install dependencies first so rebuilds reuse the cached layer
COPY app/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app/ .

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
