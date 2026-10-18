FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir uv
COPY apps/api /app
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src"
EXPOSE 8000
CMD ["uvicorn", "faultline.main:app", "--host", "0.0.0.0", "--port", "8000"]
