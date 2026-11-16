FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dsf_ai/ dsf_ai/
COPY templates/ templates/
COPY samples/ samples/
COPY app.py batch.py dashboard.py ./
ENV HOST=0.0.0.0 PORT=5000
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "600", "app:app"]
