FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
WORKDIR /app
COPY server.py /app/server.py
USER 1000:1000
EXPOSE 8768
CMD ["python", "/app/server.py"]
