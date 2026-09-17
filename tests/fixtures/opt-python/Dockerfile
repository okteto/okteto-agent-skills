# Intentionally un-optimized: unpinned base, COPY . . before installing deps.
FROM python:latest
WORKDIR /usr/src/app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
