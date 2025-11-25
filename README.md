# Agentes Backend

Sistema de agentes usando AgentPy que se comunican con el blackboard de Django. Los agentes coordinan para fumigar campos con infestación.

## Requisitos

- Docker
- Docker Compose

## Configuración con Docker

### 1. Configurar variables de entorno (opcional)

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
# Django Settings
SECRET_KEY=tu-secret-key-aqui
DEBUG=True
ALLOWED_HOSTS=*

# Database Settings
DB_NAME=agentes_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432
```

Si no creas el archivo `.env`, se usarán los valores por defecto del `docker-compose.yml`.

### 2. Construir y ejecutar los contenedores

```bash
docker-compose up --build
```

Este comando:
- Construye la imagen de la aplicación Django
- Crea y ejecuta el contenedor de PostgreSQL
- Ejecuta las migraciones de Django automáticamente
- Inicia el servidor de desarrollo en `http://localhost:8000`

### 3. Ejecutar comandos de Django

Para ejecutar comandos de Django dentro del contenedor:

```bash
# Crear un superusuario
docker-compose exec web python manage.py createsuperuser

# Ejecutar migraciones manualmente
docker-compose exec web python manage.py migrate

# Acceder a la shell de Django
docker-compose exec web python manage.py shell
```

### 4. Detener los contenedores

```bash
# Detener los contenedores
docker-compose down

# Detener y eliminar los volúmenes (incluyendo la base de datos)
docker-compose down -v
```

## Estructura de Servicios

- **web**: Aplicación Django (puerto 8000)
- **frontend**: Aplicación React (puerto 3000)
- **db**: Base de datos PostgreSQL (puerto 5432)

## Acceso a la Aplicación

Una vez que los contenedores estén ejecutándose:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/
- **Admin Django**: http://localhost:8000/admin/

## Desarrollo del Frontend

Si quieres desarrollar el frontend localmente sin Docker:

```bash
cd frontend
npm install
npm run dev
```

El frontend se ejecutará en `http://localhost:3000` y se conectará automáticamente al backend.

## Notas

- Los datos de PostgreSQL se persisten en un volumen Docker llamado `postgres_data`
- El código de la aplicación está montado como volumen, por lo que los cambios se reflejan inmediatamente
- El servidor de desarrollo de Django se reinicia automáticamente cuando detecta cambios
- El frontend usa Nginx en producción y Vite en desarrollo

