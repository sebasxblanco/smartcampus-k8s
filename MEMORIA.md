# Memoria técnica · SmartCampus con Docker Compose y Kubernetes

## 1. Introducción

SmartCampus Solutions gestiona las aulas y las reservas de espacios de una universidad. Para este prototipo la dirección exige que la aplicación pueda desplegarse con contenedores y que el equipo domine tanto Docker Compose como Kubernetes.

La solución es una aplicación de tres servicios independientes (frontend, backend y base de datos), cada uno en su propio contenedor, desplegada dos veces: con Docker Compose en un solo equipo y con Kubernetes en un clúster local de Minikube. Al final se comparan las dos herramientas con criterios técnicos.

## 2. Arquitectura

```
                         ┌──────────────┐
  navegador ──HTTP──▶    │  FRONTEND    │  nginx: sirve index.html + app.js
                         │  (puerto 80) │  y reenvía /api/* al backend
                         └──────┬───────┘
                                │ HTTP  (BACKEND_URL)
                         ┌──────▼───────┐
                         │  BACKEND     │  FastAPI: aulas y reservas,
                         │  (8000)      │  reglas de negocio
                         └──────┬───────┘
                                │ SQL  (DB_HOST:5432)
                         ┌──────▼───────┐
                         │  DATABASE    │  PostgreSQL 18 (imagen oficial)
                         │  (5432)      │  + volumen persistente
                         └──────────────┘
```

- El navegador solo habla con el frontend. nginx reenvía `/api/...` al backend, así que no hace falta CORS ni exponer el backend fuera.
- El backend lee la conexión a la base de datos de variables de entorno (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`). Ninguna dirección ni credencial está escrita en el código.
- `database/init.sql` crea las tablas y carga tres aulas y tres reservas de ejemplo.

## 3. Despliegue con Docker

### Dockerfiles e imágenes

| Servicio | Imagen | Detalles |
|---|---|---|
| backend | `smartcampus-backend` (propia, desde `python:3.12-slim`) | Instala primero `requirements.txt` para aprovechar la caché de capas; copia solo `app/`; se ejecuta con un usuario sin privilegios; `HEALTHCHECK` contra `/health` |
| frontend | `smartcampus-frontend` (propia, desde `nginx:alpine`) | La configuración es una plantilla: la imagen oficial de nginx sustituye `${BACKEND_URL}` al arrancar, así que la misma imagen sirve para Compose y para Kubernetes |
| database | `postgres:18` (oficial) | Sin Dockerfile propio |

### Docker Compose

| Elemento | Configuración |
|---|---|
| Servicios | `frontend`, `backend`, `database` |
| Redes | `frontend-net` (frontend y backend) y `backend-net` (backend y base de datos). El frontend no tiene ruta a la base de datos |
| Puertos | Frontend `8080:80`, backend `8000:8000` (para probar `/health`). PostgreSQL no se publica |
| Variables | Se leen de `.env` (plantilla en `.env.example`, el `.env` real no se versiona) |
| Dependencias | `depends_on` con `condition: service_healthy`: el backend espera a que PostgreSQL responda a `pg_isready` y el frontend al healthcheck del backend |
| Volúmenes | `db-data` para los datos de PostgreSQL y `init.sql` montado en `/docker-entrypoint-initdb.d` |
| Reinicio | `restart: unless-stopped` |

**Comunicación:** Compose crea un DNS interno en cada red. El backend llega a la base de datos con el nombre `database` y el frontend al backend con `backend`.

## 4. Despliegue con Kubernetes

| Recurso | Fichero | Para qué |
|---|---|---|
| Namespace `smartcampus` | `namespace.yaml` | Agrupa todos los recursos de la práctica y se borran de una vez |
| ConfigMap `smartcampus-config` | `configmap.yaml` | Configuración no sensible: `APP_ENV`, `BACKEND_URL`, `DB_HOST`, `DB_PORT`, `DB_NAME` |
| ConfigMap `database-init` | `database-init-configmap.yaml` | El `init.sql`, montado como fichero en el Pod de PostgreSQL |
| Secret `db-credentials` | `secret.yaml` | `DB_USER` y `DB_PASSWORD` |
| StatefulSet `database` | `database-statefulset.yaml` | PostgreSQL con 1 réplica y su volumen (PVC de 1 Gi) |
| Service `database-service` | `database-service.yaml` | Headless (`clusterIP: None`): el nombre resuelve al Pod `database-0` |
| Deployment `backend` | `backend-deployment.yaml` | **2 réplicas**, probes de readiness y liveness sobre `/health`, límites de CPU y memoria, initContainer que espera a PostgreSQL |
| Service `backend-service` | `backend-service.yaml` | ClusterIP: reparte entre las réplicas del backend, solo dentro del clúster |
| Deployment `frontend` | `frontend-deployment.yaml` | 1 réplica |
| Service `frontend-service` | `frontend-service.yaml` | **NodePort 30080**: expone el frontend fuera del clúster |

```
Navegador → frontend-service (NodePort) → Pod frontend
          → backend-service (ClusterIP) → Pods backend (x2)
          → database-service (headless) → Pod database-0 → PVC data-database-0
```

Ningún Pod habla con otro por IP: siempre a través del nombre de un Service.

**Qué lee cada uno del ConfigMap:** el backend carga el ConfigMap entero con `envFrom` (y `APP_ENV` se ve en `GET /info` y en la cabecera del frontend). El frontend lee `BACKEND_URL`.

### Deployment o StatefulSet para la base de datos

Se ha elegido **StatefulSet**:

- **Identidad estable.** El Pod se llama siempre `database-0`, aunque se borre y se recree. Con un Deployment tendría un nombre aleatorio nuevo cada vez.
- **Almacenamiento ligado al Pod.** `volumeClaimTemplates` crea un PVC por réplica (`data-database-0`) que sobrevive al Pod y se vuelve a montar en el que lo sustituye. Un Deployment comparte un mismo PVC entre todas sus réplicas, y dos PostgreSQL escribiendo en el mismo directorio corromperían los datos.
- **Orden.** Si se escalara, los Pods se crean y se borran en orden (0, 1, 2...), que es lo que necesita una réplica primaria y sus secundarias.

Para una sola réplica un Deployment con un PVC también funcionaría, pero el StatefulSet expresa mejor lo que es una base de datos y permite crecer sin rediseñar.

### Secrets: para qué sirven y sus limitaciones

Un Secret separa las credenciales de la imagen y del manifiesto del Deployment: el contenedor las recibe como variables de entorno (`secretKeyRef`) y se pueden cambiar sin reconstruir nada. También permite dar permisos de lectura (RBAC) distintos a los de un ConfigMap.

Limitaciones:

- **Base64 no es cifrado.** `kubectl get secret db-credentials -o yaml` y un `base64 -d` devuelven la contraseña en claro.
- **En etcd se guardan sin cifrar por defecto**, salvo que se active el cifrado en reposo (`EncryptionConfiguration`).
- Cualquiera con permiso para leer Secrets en el namespace, o para crear Pods que los monten, puede verlos.
- **Versionar `secret.yaml` es un riesgo.** En esta práctica se versiona con una contraseña de laboratorio solo válida en Minikube, y está avisado en el propio fichero. En un entorno real se usaría un gestor externo como **HashiCorp Vault** o **AWS Secrets Manager** (con External Secrets Operator), o se cifraría el manifiesto con Sealed Secrets o SOPS.

## 5. Pruebas

> Capturas en `docs/evidencias/`.

### Docker

| # | Prueba | Resultado | Captura |
|---|---|---|---|
| D1 | `docker compose up -d` y `docker compose ps` | _pendiente_ | `d1-compose-ps.png` |
| D2 | `/health` | _pendiente_ | `d2-health.png` |
| D3 | Backend ↔ BD (`/rooms` devuelve los datos de `init.sql`) | _pendiente_ | `d3-rooms.png` |
| D4 | Frontend en el navegador | _pendiente_ | `d4-frontend.png` |
| D5 | Persistencia: crear un aula, `down`, `up` | _pendiente_ | `d5-persistencia.png` |
| D6 | `docker stop` del backend | _pendiente_ | `d6-stop.png` |

### Kubernetes

| # | Experimento | Resultado | Captura |
|---|---|---|---|
| K1 | `kubectl apply -f k8s/`, `get pods`, `get services`, `get deployments`, frontend en el navegador | Todo en `Running`; `/api/health`, `/api/rooms` y `/api/bookings` responden a través del NodePort (20 oct) | `k1-*.png` |
| K2 | Escalar el backend a 4 réplicas y volver a 2 | _pendiente_ | `k2-escalado.png` |
| K3 | Borrar un Pod del backend | _pendiente_ | `k3-self-healing.png` |
| K4 | Cambiar `APP_ENV` en el ConfigMap | _pendiente_ | `k4-configmap.png` |

## 6. Comparativa Docker Compose y Kubernetes

| Característica | Docker Compose | Kubernetes |
|---|---|---|
| Ejecución local | Nativa: un `docker compose up` en el propio equipo, arranque en segundos | Necesita un clúster local (Minikube, Kind); más recursos y más pasos |
| Orquestación | Arranca y para contenedores en **un solo host** según el YAML; no reacciona a fallos más allá de la política `restart` | Bucle de control que compara continuamente el estado deseado con el real y lo corrige, en **varios nodos** |
| Escalado | Manual (`--scale`), en un solo host; choca con los puertos publicados fijos | `kubectl scale` o automático con HPA según CPU o memoria; reparte réplicas entre nodos |
| Self-healing | Solo reinicia contenedores que terminan, y solo con `restart:`. Un `docker stop` manual no se recupera | El ReplicaSet recrea los Pods que faltan; las probes reinician los que no responden y los sacan del balanceo |
| Service discovery | DNS interno por nombre de servicio dentro de la red de Compose | DNS del clúster por nombre de Service (`backend-service.smartcampus.svc.cluster.local`), con IP virtual estable |
| Configuración | Variables de entorno y `.env` | ConfigMaps, versionables y compartibles entre Pods, separados de la imagen |
| Secrets | Variables o el `.env` en el disco; los `secrets` de Compose son ficheros montados, sin gestión central | Objeto Secret con RBAC e integrable con gestores externos, aunque en base64 por defecto |
| Alta disponibilidad | No: si cae el host, cae todo | Réplicas repartidas en varios nodos; si cae un nodo, los Pods se reprograman en otro |
| Balanceo | No hay balanceo real entre réplicas con puerto publicado; haría falta un proxy propio | El Service balancea entre los Pods listos (readiness) |
| Actualizaciones | `up` recrea los contenedores, con corte | Rolling update sin corte (`maxUnavailable`/`maxSurge`) y `rollout undo` para volver atrás |
| Complejidad | Baja: un fichero, pocos conceptos | Alta: muchos recursos, YAML extenso, red y almacenamiento propios |
| Uso habitual | Desarrollo local, pruebas, demos, proyectos pequeños en un servidor | Producción con varios servicios, varios nodos y requisitos de disponibilidad y escalado |

## 7. Problemas encontrados

### 7.1 De comunicación entre servicios: `No route to host` en Docker Compose

- **Síntoma:** al levantar el Compose en el portátil (Fedora), el backend entra en bucle de reinicio. En `docker compose logs backend`: `psycopg.OperationalError: connection to server at "172.19.0.2", port 5432 failed: No route to host`. La base de datos estaba `healthy`.
- **Diagnóstico:** el error no es de credenciales ni de que PostgreSQL no estuviera listo (eso daría `connection refused` o `authentication failed`): es la red la que rechaza el paquete. `firewall-cmd --info-zone=docker` mostraba la zona `docker` sin ninguna interfaz, así que el puente de la red de Compose quedaba fuera de ella y firewalld rechazaba el tráfico entre contenedores. El mismo Compose funcionaba en el runner de GitHub Actions (Ubuntu, sin firewalld), lo que confirmaba que el fichero estaba bien.
- **Solución:** _pendiente de aplicar y comprobar_ (`sudo systemctl restart docker`, para que Docker vuelva a registrar sus redes en firewalld).

### 7.2 Al construir las imágenes

_Pendiente: anotar al encontrarlo._

### 7.3 Durante el despliegue

_Pendiente: anotar al encontrarlo._

### 7.4 En Kubernetes

_Pendiente: anotar al encontrarlo._

## 8. Conclusiones

| Escenario | Tecnología | Por qué |
|---|---|---|
| Desarrollo local | Docker Compose | Arranca en segundos con un comando, poco consumo, el mismo fichero para todo el equipo |
| Pruebas | Docker Compose (y Kubernetes en un entorno de staging) | Compose levanta un entorno desechable en CI; si producción es Kubernetes, conviene una fase de prueba con los mismos manifiestos |
| Proyecto personal pequeño | Docker Compose | Un servidor basta; Kubernetes añadiría complejidad sin beneficio |
| Aplicación empresarial con varios servicios | Kubernetes | Self-healing, rolling updates, RBAC, Secrets y descubrimiento de servicios para muchos equipos y servicios |
| Aplicación que necesita escalar | Kubernetes | Escalado horizontal (incluso automático con HPA) y balanceo entre réplicas y nodos |

## 9. Preguntas

**Conceptos básicos**

1. **Contenedor Docker frente a Pod.** Un contenedor es un proceso aislado creado a partir de una imagen. Un Pod es la unidad mínima de Kubernetes: envuelve uno o varios contenedores que comparten IP, puertos y volúmenes, y Kubernetes lo programa, vigila y sustituye. El Pod es desechable: no se repara, se reemplaza.
2. **Qué resuelve Docker Compose.** Definir y arrancar una aplicación de varios contenedores en un solo host con un único fichero declarativo y un único comando: redes, volúmenes, variables, dependencias y orden de arranque, sin encadenar `docker run` a mano.
3. **Qué añade Kubernetes.** Orquestación en varios nodos: mantener el estado deseado (self-healing), escalado manual y automático, balanceo, descubrimiento de servicios, actualizaciones sin corte con vuelta atrás, gestión de configuración y Secrets, y alta disponibilidad ante la caída de un nodo.

**Recursos de Kubernetes**

8. **Deployment.** Declara cuántas réplicas de un Pod deben existir y con qué plantilla. Crea un ReplicaSet que mantiene ese número, y gestiona las actualizaciones (rolling update) y las vueltas atrás.
9. **Service.** Da un nombre DNS y una IP virtual estables a un conjunto variable de Pods (los que cumplen su `selector`) y reparte el tráfico entre los que están listos. Según el tipo, lo expone solo dentro del clúster (ClusterIP) o fuera (NodePort, LoadBalancer).
6. **Descubrimiento de servicios.** El DNS del clúster (CoreDNS) crea un registro por cada Service: `<service>.<namespace>.svc.cluster.local`, o solo `<service>` dentro del mismo namespace. Los Pods también reciben variables de entorno con los Services que ya existían al arrancar.
7. **Por qué no usar la IP de un Pod.** Es efímera: cambia cada vez que el Pod se recrea (fallo, escalado, actualización). Además, con varias réplicas, apuntar a una IP concreta se salta el balanceo. El Service da una dirección estable.
12. **ConfigMap y Secret.** Separan la configuración de la imagen: la misma imagen sirve para varios entornos cambiando solo estos objetos. El ConfigMap guarda los datos no sensibles; el Secret, las credenciales, con permisos aparte y la opción de cifrarlos en reposo.

**Estado y datos**

10. **Deployment frente a StatefulSet.** El Deployment trata a sus Pods como intercambiables: nombres aleatorios, sin orden, un volumen compartido si lo hay. El StatefulSet les da identidad estable (`nombre-0`, `nombre-1`), DNS propio por Pod con un Service headless, un volumen persistente por réplica que sigue al Pod, y creación y borrado ordenados.
11. **Por qué una base de datos es distinta de una API stateless.** La API no guarda nada entre peticiones: cualquier réplica puede atender y se puede destruir o duplicar sin perder nada. La base de datos sí guarda estado. Si se pierde el Pod, los datos tienen que seguir en un volumen persistente, cada instancia necesita su propio almacenamiento y la replicación exige identidades y orden estables.

**Fallos y recuperación**

4. **Borrar a mano un contenedor de Compose.** Con `docker rm -f` o `docker stop`, Compose no lo recrea: no hay un proceso vigilando el estado deseado. `restart: always` o `unless-stopped` solo reinician un contenedor que termina por sí mismo, no uno parado a mano. Vuelve con el siguiente `docker compose up`.
5. **Borrar un Pod de un Deployment.** El ReplicaSet detecta que hay menos réplicas de las declaradas y crea un Pod nuevo al momento, con otro nombre y otra IP. El Service deja de enviarle tráfico al viejo y lo envía al nuevo cuando pasa la readiness.
15. **Cuando un Pod falla.** Si el contenedor termina, el kubelet lo reinicia según la `restartPolicy` (con espera creciente, `CrashLoopBackOff`). Si la liveness probe falla, lo reinicia aunque el proceso siga vivo. Si falla la readiness, lo saca del Service sin matarlo. Si cae el nodo entero, el controlador crea el Pod en otro nodo.

**Escalado**

13. **Escalar con Compose.** `docker compose up -d --scale backend=3`, a mano y en un solo host. Choca con los puertos publicados fijos (solo un contenedor puede tener el `8000` del host) y no hay balanceo entre réplicas sin añadir un proxy.
14. **Escalar con Kubernetes.** `kubectl scale deployment backend --replicas=4` o cambiar `replicas` en el YAML; automáticamente con un HorizontalPodAutoscaler según CPU o memoria. El Service incluye las réplicas nuevas en el balanceo en cuanto están listas.

**Valoración**

16. **Ventajas de Kubernetes con varios servicios.** Descubrimiento por nombre, escalado y self-healing por servicio, actualizaciones independientes sin corte, configuración y Secrets centralizados, namespaces y RBAC para separar equipos, y el mismo modelo en cualquier proveedor de nube.
17. **Inconvenientes frente a Compose.** Curva de aprendizaje y volumen de YAML mucho mayores, más recursos (plano de control), más difícil de depurar (red, DNS, almacenamiento) y coste de operación. Para un solo host es desproporcionado.
18. **Cuándo Docker Compose.** Desarrollo local, entornos de prueba en CI, demos y aplicaciones pequeñas en un único servidor, sin requisitos de alta disponibilidad.
19. **Cuándo Kubernetes.** Producción con varios servicios, varios nodos, tráfico variable que obliga a escalar y necesidad de disponibilidad y despliegues sin corte.
20. **Del entorno local a la nube.** Subir las imágenes a un registro (Docker Hub, ECR) en lugar de construirlas en Minikube y quitar `imagePullPolicy: Never`; usar un clúster gestionado (EKS, AKS, GKE); exponer el frontend con un LoadBalancer o un Ingress con TLS; usar una StorageClass del proveedor para los volúmenes o una base de datos gestionada (RDS); sacar los Secrets a un gestor (AWS Secrets Manager con External Secrets); añadir HPA, monitorización (Prometheus y Grafana) y un pipeline de CI/CD que despliegue los manifiestos.
