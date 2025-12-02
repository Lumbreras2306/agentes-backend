# Frontend - Sistema de Agentes

Frontend desarrollado con React + TypeScript + Vite para visualizar y gestionar simulaciones de agentes.

## Características

- 🌍 **Gestión de Mundos**: Crear, visualizar y gestionar mundos con campos, caminos e infestación
- 🤖 **Simulaciones**: Ejecutar y monitorear simulaciones con agentes fumigadores (sin drones ni scouts)
- 🎬 **Animaciones**: Visualizar animaciones de pathfinding con múltiples tractores usando Dijkstra
- 📊 **Visualización en Tiempo Real**: Ver agentes y tareas en el mundo en tiempo real
- 🎨 **Interfaz Moderna**: UI moderna y responsiva con animaciones suaves

## Tecnologías

- **React 18** - Biblioteca de UI
- **TypeScript** - Tipado estático
- **Vite** - Build tool y dev server
- **React Router** - Navegación
- **Framer Motion** - Animaciones
- **Axios** - Cliente HTTP
- **Canvas API** - Visualización del mundo

## Desarrollo

### Instalación

```bash
npm install
```

### Ejecutar en desarrollo

```bash
npm run dev
```

El frontend estará disponible en `http://localhost:3000`

### Construir para producción

```bash
npm run build
```

Los archivos se generarán en la carpeta `dist/`

### Preview de producción

```bash
npm run preview
```

## Estructura del Proyecto

```
frontend/
├── src/
│   ├── components/      # Componentes reutilizables
│   │   ├── Layout.tsx   # Layout principal con navegación
│   │   └── WorldVisualization.tsx  # Visualización del mundo con canvas
│   ├── pages/           # Páginas de la aplicación
│   │   ├── Home.tsx     # Página de inicio
│   │   ├── Worlds.tsx    # Lista de mundos
│   │   ├── WorldDetail.tsx  # Detalle del mundo con visualización
│   │   ├── Simulations.tsx  # Lista de simulaciones
│   │   └── SimulationDetail.tsx  # Detalle de simulación
│   ├── services/        # Servicios API
│   │   └── api.ts       # Cliente API con todos los endpoints
│   ├── types/           # Tipos TypeScript
│   │   └── index.ts     # Definiciones de tipos
│   ├── App.tsx          # Componente raíz
│   └── main.tsx         # Punto de entrada
├── public/              # Archivos estáticos
├── Dockerfile           # Docker para producción
├── nginx.conf           # Configuración de Nginx
└── package.json         # Dependencias
```

## API Endpoints

El frontend se comunica con el backend a través de los siguientes endpoints:

- `/api/worlds/` - Gestión de mundos
- `/api/agents/` - Información de agentes
- `/api/simulations/` - Gestión de simulaciones
- `/api/blackboard/` - Tareas del blackboard

## Variables de Entorno

Crea un archivo `.env` en la raíz del frontend:

```env
VITE_API_URL=http://localhost:8000/api
```

Si no se define, se usa `/api` como ruta relativa (útil con proxy de Vite).

