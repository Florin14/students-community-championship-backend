FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY alembic.ini /app/

ENV PYTHONPATH=/app/src
WORKDIR /app/src

EXPOSE 8000

CMD ["uvicorn", "services.run_api:api", "--host", "0.0.0.0", "--port", "8000"]
