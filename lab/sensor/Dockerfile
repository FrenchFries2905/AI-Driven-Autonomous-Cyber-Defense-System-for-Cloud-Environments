# Sensor image: scapy (packet capture) + requests (posting to the API)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /sensor
RUN pip install scapy requests
COPY sensor.py .

CMD ["python", "sensor.py"]
