FROM python:3.12-slim

WORKDIR /workspace/backend

COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY data /workspace/data
COPY backend /workspace/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
