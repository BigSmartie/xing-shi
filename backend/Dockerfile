FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/code

WORKDIR /code

COPY backend/requirements.txt /code/backend/requirements.txt
RUN pip install --no-cache-dir -r /code/backend/requirements.txt

COPY backend /code/backend

EXPOSE 9000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "9000"]

