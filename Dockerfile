FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
COPY omnivoice ./omnivoice
RUN pip install --no-cache-dir -c requirements.lock '.[semantic]' && useradd --create-home omni && mkdir -p data models && chown -R omni:omni /app
USER omni
EXPOSE 8000
CMD ["omnivoice", "serve", "--host", "0.0.0.0"]
