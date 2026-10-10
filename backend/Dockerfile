FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY asclepius ./asclepius
RUN pip install --no-cache-dir .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "asclepius.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
