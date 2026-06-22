FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 2>&1 | tail -1

COPY . .

# Use the Docker config
ENV DJANGO_SETTINGS_MODULE=netbox.settings
ENV NETBOX_CONFIGURATION=netbox.configuration_docker

# Create static dir
RUN mkdir -p /app/netbox/project-static/docs

WORKDIR /app/netbox

RUN python manage.py migrate --noinput 2>&1 | tail -5
RUN python -c "from users.models import User; User.objects.create_superuser('admin','admin@lab.local','Admin123!') if not User.objects.filter(username='admin').exists() else print('admin exists')"

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
