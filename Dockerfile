# panelexemys/Dockerfile
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends iputils-ping curl tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY timeauthority-pkg /timeauthority-pkg
COPY panelexemys/requirements.txt /app/requirements.txt
RUN pip install --no-compile -r /app/requirements.txt

RUN useradd -m -u 10001 appuser

COPY panelexemys/src /app/src
COPY panelexemys/config.py /app/config.py

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8052

CMD ["waitress-serve", "--listen=0.0.0.0:8052", "src.app:server"]
