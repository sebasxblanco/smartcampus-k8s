# SmartCampus · Docker Compose y Kubernetes

Prototipo de la plataforma de aulas y reservas de SmartCampus Solutions, desplegado de dos formas: con Docker Compose y con Kubernetes (Minikube). La memoria técnica, con la comparativa y las preguntas, está en [MEMORIA.md](MEMORIA.md).

## Arquitectura

```
navegador ──▶ FRONTEND (nginx) ──/api/──▶ BACKEND (FastAPI) ──SQL──▶ DATABASE (PostgreSQL)
```

| Carpeta | Contenido |
|---|---|
| `frontend/` | Página HTML + JavaScript servida por nginx. nginx reenvía `/api/` al backend (`BACKEND_URL`) |
| `backend/` | API REST en FastAPI con tests (pytest). Endpoints: `GET /health`, `/info`, `/rooms`, `/rooms/{id}`, `/bookings`, y `POST`/`DELETE` de aulas y reservas |
| `database/init.sql` | Crea las tablas `rooms` y `bookings` y carga datos de ejemplo |
| `docker-compose.yml` | Despliegue con Docker Compose |
| `k8s/` | Manifiestos de Kubernetes |

## Despliegue con Docker Compose

```bash
cp .env.example .env                 # poner una contraseña real en DB_PASSWORD
docker compose up --build -d
docker compose ps                    # los 3 servicios en marcha
```

- Frontend: http://localhost:8080
- Backend: http://localhost:8000/health · http://localhost:8000/docs

Si otro proyecto ya usa el 8000 o el 8080, cambiar `BACKEND_PORT` y `FRONTEND_PORT` en el `.env`.

## Despliegue con Kubernetes (Minikube)

```bash
minikube start

# Las imágenes se construyen dentro de Minikube (imagePullPolicy: Never)
minikube image build -t smartcampus-backend:latest backend/
minikube image build -t smartcampus-frontend:latest frontend/

kubectl apply -f k8s/namespace.yaml  # primero el namespace: el resto vive dentro
kubectl apply -f k8s/
kubectl -n smartcampus get pods,services,deployments,statefulsets

minikube service frontend-service -n smartcampus   # abre el frontend en el navegador
```

El frontend queda en `http://<minikube ip>:30080`.

### Experimentos

```bash
# Escalado
kubectl -n smartcampus scale deployment backend --replicas=4
kubectl -n smartcampus get pods
kubectl -n smartcampus scale deployment backend --replicas=2

# Self-healing
kubectl -n smartcampus delete pod <pod-del-backend>
kubectl -n smartcampus get pods

# ConfigMap
kubectl -n smartcampus edit configmap smartcampus-config    # cambiar APP_ENV
kubectl -n smartcampus rollout restart deployment backend   # los Pods lo leen al arrancar
```

### Limpiar

```bash
kubectl delete namespace smartcampus
docker compose down -v
```

## Tests del backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Evidencias

Capturas en `docs/evidencias/` (ver la sección 5 de la memoria).
