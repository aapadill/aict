FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app ./app
COPY data/corpus ./data/corpus

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8001"]
