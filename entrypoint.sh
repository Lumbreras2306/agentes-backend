#!/bin/bash
set -e

echo "Esperando a que la base de datos esté lista..."

# Esperar a que PostgreSQL esté listo
until python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(
        dbname=os.environ.get('DB_NAME', 'agentes_db'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'postgres'),
        host=os.environ.get('DB_HOST', 'db'),
        port=os.environ.get('DB_PORT', '5432')
    )
    conn.close()
    print('Base de datos lista!')
except psycopg2.OperationalError:
    exit(1)
" 2>/dev/null; do
  echo "Esperando a PostgreSQL..."
  sleep 1
done

echo "Creando migraciones si es necesario..."
python manage.py makemigrations agents world || true

echo "Ejecutando migraciones..."
python manage.py migrate --noinput

echo "Migraciones completadas. Ejecutando comando: $@"
exec "$@"

