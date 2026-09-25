FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY Passenger/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 ridenova
COPY Passenger/backend/ ./
USER ridenova
EXPOSE 10000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:create_app()"]
