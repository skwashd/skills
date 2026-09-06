FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

COPY . .
CMD ["uvicorn", "acme_api:app", "--host", "0.0.0.0"]
