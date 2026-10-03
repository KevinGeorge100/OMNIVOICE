FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
COPY omnivoice ./omnivoice
RUN pip install --no-cache-dir -c requirements.lock '.[semantic]' && \
    python -m omnivoice.cli models && \
    useradd --create-home omni && \
    mkdir -p data && \
    chown -R omni:omni /app
USER omni
VOLUME ["/app/data"]
EXPOSE 8000
CMD ["omnivoice", "serve", "--host", "0.0.0.0", "--port", "8000"]
