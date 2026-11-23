FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# CPU-only build of llama.cpp; native AVX2 is detected at build time on the VPS.
RUN CMAKE_ARGS="-DGGML_NATIVE=ON" pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y build-essential cmake && apt-get autoremove -y

COPY review_worker ./review_worker
RUN useradd --uid 10001 --create-home worker && mkdir -p /data /models && chown worker /data
USER worker
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4
EXPOSE 8090
CMD ["uvicorn", "review_worker.app:app", "--host", "0.0.0.0", "--port", "8090", "--workers", "1"]
