FROM python:3.12-slim
RUN pip install --no-cache-dir pillow pillow-heif
COPY server.py /app/server.py
EXPOSE 8128
CMD ["python", "/app/server.py"]
