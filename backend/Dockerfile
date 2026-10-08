FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements/base.txt /app/requirements/base.txt
RUN pip install --no-cache-dir -r /app/requirements/base.txt

COPY app /app/app
COPY alembic.ini /app/alembic.ini

EXPOSE 8000

CMD ["sh", "-c", "python -m app.utils.check_migrations && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
