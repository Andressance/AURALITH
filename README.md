# AURALITH

# Personal Music Cloud

> **Tu música. Tu servidor. Tus reglas.**
>
> **Your music. Your server. Your rules.**

## English

AURALITH is a self-hosted, open-source platform for storing and playing a personal music library. The MVP is designed for one owner: secure login, private MP3/FLAC uploads, metadata extraction, playlists, favorites, HTTP Range playback, SQLite backups/restores, and Docker deployment.

### Quick start

Requirements: Docker Compose.

```bash
AURALITH_OWNER_PASSWORD="choose-a-secure-password" docker compose up --build
```

Open `http://localhost:8080`. The owner username defaults to `owner` and can be changed with `AURALITH_OWNER_USERNAME`.

The stack stores data in the `auralith-data` Docker volume. Backups and restores are available from `/api/backup` and `/api/restore` for the SQLite deployment.

### Providers

The backend is not coupled to Supabase or to a local installation:

- Set `AURALITH_DB_URL` to any SQLAlchemy-compatible PostgreSQL or SQLite URL.
- Set `AURALITH_STORAGE_PROVIDER=local` for filesystem storage.
- Set `AURALITH_STORAGE_PROVIDER=supabase` and provide `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, and `SUPABASE_STORAGE_BUCKET` for Supabase Storage. `SUPABASE_SERVICE_ROLE_KEY` remains accepted only as deprecated compatibility.
- Supabase PostgreSQL uses a regular PostgreSQL `AURALITH_DB_URL`; an optional adapter can later enable Supabase-specific features without changing the API modules.

### MVP scope

- One owner account
- Password authentication with Argon2 and HTTP-only sessions
- MP3 and FLAC uploads
- Mutagen metadata extraction
- Owner-only library isolation
- Range-based audio streaming
- Playlists and favorites
- ZIP backup and SQLite restore
- Docker Compose deployment

The detailed architecture, security model, roadmap, and future federation design remain in Spanish below.

### Deployment

#### Supabase + Render

1. Create a PostgreSQL database in Supabase and configure `AURALITH_DB_URL` with the PostgreSQL connection string.
2. Apply `supabase/migrations/202611230001_initial.sql`.
3. Create a private Supabase Storage bucket named `music`.
4. Deploy `apps/api` to Render using `render.yaml` or the Dockerfile.
5. Set `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_STORAGE_BUCKET`, `AURALITH_OWNER_PASSWORD`, `AURALITH_CORS_ORIGINS=https://<your-vercel-app>.vercel.app`, and `AURALITH_COOKIE_SAMESITE=none`.
6. Deploy `apps/web` on Vercel and set `VITE_API_URL=https://<your-render-service>.onrender.com`.
7. Never expose `SUPABASE_SECRET_KEY` to the frontend.

For Render, use a **Web Service** with:

- **Root Directory:** leave it blank.
- **Language/Environment:** Docker.
- **Dockerfile Path:** `apps/api/Dockerfile`.
- **Docker Build Context Directory:** `.`
- **Health Check Path:** `/api/health`.

Do not select `apps/api` as the root directory. The Docker build needs the repository root to copy `pyproject.toml` and the `apps` package.

#### Local Docker

```bash
cp .env.example .env
AURALITH_OWNER_PASSWORD="change-this-password" docker compose up --build
```

Open `http://localhost:8080`. The SQLite database and music files are stored in the `auralith-data` Docker volume.

---

## Español

## 1. Visión del proyecto

AURALITH es una plataforma de streaming musical personal, self-hosted y open source, que permite almacenar, organizar, importar y reproducir música desde una biblioteca propia.

La plataforma busca ofrecer una experiencia similar a los servicios comerciales de streaming, pero sin depender de suscripciones, algoritmos propietarios ni plataformas centralizadas.

Cada instalación pertenece a una persona que administra su propia instancia y puede compartirla con familiares o amigos de confianza.

El objetivo inicial es construir una plataforma que funcione perfectamente para un pequeño grupo de usuarios, con bibliotecas privadas, cuentas independientes, reproducción fluida y una experiencia moderna tanto en ordenador como en móvil.

La plataforma debe ser modular, segura, extensible y preparada para evolucionar hacia funcionalidades sociales descentralizadas en futuras versiones.

### Principios fundamentales

- **Self-hosted:** cada usuario puede alojar su propia instancia.
- **Privacy-first:** la privacidad es la configuración predeterminada.
- **Multi-user:** una instancia puede tener varios usuarios.
- **Open source:** código abierto y posibilidad de modificarlo.
- **Modular:** componentes independientes con interfaces claras.
- **Provider-agnostic:** integraciones sustituibles.
- **Security by design:** seguridad desde la arquitectura inicial.
- **Mobile-first:** experiencia optimizada para móvil.
- **Efficient:** infraestructura ligera y uso eficiente de recursos.
- **Extensible:** preparada para incorporar nuevas funcionalidades.
- **No central dependency:** el funcionamiento principal no depende de un servidor central del proyecto.

---

# 2. Alcance del proyecto

El proyecto se dividirá en versiones para evitar construir funcionalidades complejas antes de tener una aplicación funcional.

## V1 — Personal Music Cloud

La primera versión estará enfocada en crear una plataforma musical completamente funcional para uso personal y para compartir una instancia con familiares y amigos.

La prioridad será que la aplicación funcione perfectamente antes de añadir funcionalidades sociales avanzadas.

### Objetivo de V1

Una persona instala y administra su instancia.

Puede crear cuentas para sus padres, amigos u otros usuarios de confianza.

Cada usuario puede:

- Acceder a su propio perfil.
- Configurar su contraseña.
- Tener una biblioteca musical independiente.
- Subir su música.
- Organizarla.
- Crear playlists.
- Marcar favoritos.
- Importar playlists externas.
- Reproducir música.
- Utilizar la aplicación desde ordenador y móvil.
- Mantener su propia configuración y dashboard.

El administrador gestiona la instancia y sus usuarios, pero no tiene acceso automático a las bibliotecas privadas de los demás usuarios.

### Funcionalidades principales de V1

- Sistema de usuarios y autenticación.
- Gestión de instancias.
- Multiusuario.
- Creación y activación de cuentas.
- Sesiones persistentes y seguras.
- Dashboard personal.
- Biblioteca musical privada.
- Subida de música.
- Extracción de metadatos.
- Gestión de artistas, álbumes, canciones y géneros.
- Portadas.
- Detección de duplicados.
- Búsqueda.
- Reproductor global.
- Cola de reproducción.
- Shuffle y repeat.
- Playlists.
- Favoritos.
- Importación de playlists mediante CSV.
- Integración con proveedores externos cuando sea posible.
- Matching de canciones importadas.
- PWA.
- Compatibilidad móvil.
- Compartición controlada de playlists.
- Configuración de instancia.
- Gestión de usuarios.
- Backup y restauración.
- Documentación de instalación y self-hosting.

---

## V2 — Social y descentralización

La segunda versión ampliará la plataforma hacia una experiencia social sin necesidad de una infraestructura centralizada.

El objetivo será permitir que usuarios de diferentes instancias de Personal Music Cloud puedan encontrarse, añadirse como amigos e interactuar.

Cada instalación seguirá siendo independiente.

### Funcionalidades previstas

- Sistema de amigos entre diferentes instancias.
- Identidad federada.
- Solicitudes de amistad remotas.
- Aceptación y rechazo de solicitudes.
- Eliminación de amigos.
- Bloqueo de usuarios.
- Perfiles públicos configurables.
- Compartición de playlists entre instancias.
- Compartición de canciones y álbumes.
- Gestión de permisos remotos.
- Descubrimiento de otras instancias.
- Comunicación segura entre servidores.
- API de federación.
- Firma y validación de solicitudes.
- Protección contra spam y abuso.
- Rate limiting.
- Control de privacidad para perfiles remotos.

### Identidad federada

Cada usuario podrá identificarse mediante una identidad única asociada a su instancia.

Ejemplo:

```text
@andres@music.example.com
@juan@music-server.net
@alice@personal-audio.org
```

Los usuarios podrán añadir amigos independientemente de dónde esté alojada su instancia.

La federación no requerirá una base de datos central que almacene todos los usuarios.

### Principio de federación

```text
Instancia A                       Instancia B
┌──────────────────┐             ┌──────────────────┐
│ Personal Music   │             │ Personal Music   │
│ Cloud            │             │ Cloud            │
│                  │             │                  │
│ Andrés           │◄───────────►│ Juan             │
│                  │             │                  │
│ Biblioteca       │             │ Biblioteca       │
│ privada          │             │ privada          │
└──────────────────┘             └──────────────────┘
```

La relación social no implica automáticamente acceso a las bibliotecas.

Cada usuario decide qué compartir.

---

# 3. Modelo de instancias

Cada instalación de Personal Music Cloud constituye una instancia independiente.

Una instancia puede estar alojada en:

- Un servidor personal.
- Un VPS.
- Un ordenador doméstico.
- Un NAS.
- Un servidor Docker en el futuro.

La instancia tendrá un propietario responsable de su administración.

## Modos de funcionamiento

### Personal

Una única persona utiliza la instancia.

### Private Multi-user

El propietario invita a otros usuarios.

El acceso estará limitado a las personas autorizadas.

El modo multiusuario será el principal objetivo de V1, ya que permitirá compartir la infraestructura con familiares y amigos.

---

# 4. Roles y permisos

## OWNER

Propietario de la instancia.

Puede:

- Gestionar la instancia.
- Crear usuarios.
- Invitar usuarios.
- Suspender usuarios.
- Eliminar usuarios.
- Gestionar roles.
- Configurar cuotas.
- Gestionar almacenamiento.
- Configurar integraciones globales.
- Configurar seguridad.
- Gestionar permisos de compartición.
- Gestionar backups.
- Configurar la instancia.

El OWNER no tendrá acceso automático a:

- Bibliotecas privadas.
- Playlists privadas.
- Favoritos privados.
- Historial privado.
- Estadísticas personales.
- Tokens de proveedores de otros usuarios.

## ADMIN

Administrador delegado.

Puede realizar las tareas administrativas que le conceda el propietario.

No tendrá acceso automático a los datos privados de otros usuarios.

## MEMBER

Usuario normal.

Puede:

- Gestionar su biblioteca.
- Subir música.
- Crear playlists.
- Gestionar favoritos.
- Importar playlists.
- Gestionar integraciones personales.
- Configurar su perfil.
- Configurar su dashboard.
- Compartir recursos explícitamente.

---

# 5. Sistema de cuentas

## Creación de usuarios

El administrador podrá crear usuarios desde el frontend.

Por ejemplo:

```text
Administración
    └── Usuarios
          └── Crear usuario
```

Datos iniciales:

- Username.
- Display name.
- Email opcional.
- Rol.
- Estado.
- Cuota de almacenamiento.

El usuario no tendrá que registrarse públicamente.

La creación de cuentas estará controlada por el administrador.

## Activación de cuenta

Las cuentas creadas por el administrador tendrán inicialmente el estado:

```text
PENDING_ACTIVATION
```

Cuando el usuario acceda por primera vez a su perfil:

1. Seleccionará su usuario.
2. La aplicación comprobará que la cuenta está pendiente de activación.
3. Se mostrará un formulario para establecer su contraseña.
4. El usuario establecerá su propia contraseña.
5. El backend almacenará únicamente el hash seguro de la contraseña.
6. La cuenta pasará a estado `ACTIVE`.
7. Se creará una sesión autenticada.

El administrador nunca conocerá ni podrá consultar la contraseña del usuario.

### Estados de cuenta

```text
PENDING_ACTIVATION
ACTIVE
SUSPENDED
DISABLED
DELETED
```

---

# 6. Autenticación y sesiones

## Selector de perfiles

La aplicación contará con una pantalla inicial para seleccionar el usuario.

```text
┌────────────────────────────────────────┐
│         PERSONAL MUSIC CLOUD          │
│                                      │
│          ¿Quién está escuchando?      │
│                                      │
│       [ Andrés ]    [ Mamá ]         │
│                                      │
│       [ Papá ]      [ Invitado ]     │
│                                      │
└────────────────────────────────────────┘
```

El selector de perfiles será una comodidad de UX, no un mecanismo de autenticación.

## Primer acceso

Cuando un usuario acceda por primera vez:

- Seleccionará su perfil.
- Establecerá su contraseña si su cuenta está pendiente.
- Iniciará sesión.
- La aplicación podrá recordar su sesión en ese dispositivo.

## Accesos posteriores

Cuando un usuario seleccione su perfil:

- Si existe una sesión válida, accederá directamente.
- Si la sesión ha expirado, deberá autenticarse.
- Si la sesión ha sido revocada, deberá iniciar sesión nuevamente.

## Sesiones

Las sesiones serán independientes por dispositivo.

Se podrá:

- Recordar el usuario.
- Mantener una sesión persistente.
- Cerrar sesión.
- Revocar sesiones.
- Cerrar todas las sesiones.
- Consultar dispositivos conectados.

La autenticación deberá utilizar mecanismos seguros de sesión, rotación de refresh tokens y revocación.

---

# 7. Dashboard personal

Cada usuario tendrá su propio dashboard.

El dashboard no será una vista compartida entre usuarios.

## Widgets posibles

- Welcome.
- Continue listening.
- Recently played.
- Favorites.
- Recent albums.
- Recent artists.
- Playlists.
- Recently added.
- Shared with me.
- Listening statistics.
- Friends.
- Recomendaciones futuras.

El dashboard será personalizable.

El usuario podrá decidir qué widgets mostrar y cómo organizarlos.

---

# 8. Biblioteca musical

Cada usuario tendrá una biblioteca independiente.

La biblioteca estará organizada mediante entidades lógicas, independientemente de cómo se almacenen físicamente los archivos.

## Entidades principales

### Artists

- ID.
- Nombre.
- Imagen.
- Metadata.
- Relaciones con álbumes y canciones.

### Albums

- ID.
- Nombre.
- Artista.
- Año.
- Portada.
- Metadata.

### Tracks

- ID.
- Título.
- Artista.
- Álbum.
- Duración.
- Géneros.
- Metadata.
- Identificadores externos.

### Track Files

- ID.
- Track ID.
- Storage provider.
- Storage key.
- Formato.
- Tamaño.
- Bitrate.
- Hash.
- Estado.

### Genres

- ID.
- Nombre.

## Formatos iniciales

- MP3.
- FLAC.
- M4A/AAC.
- WAV.
- OGG/Vorbis.
- Opus.

La arquitectura permitirá añadir nuevos formatos.

---

# 9. Subida e ingestión musical

El usuario podrá subir archivos musicales desde la aplicación.

## Flujo de ingestión

```text
Upload
   │
   ▼
Validation
   │
   ▼
Metadata Extraction
   │
   ▼
Normalization
   │
   ▼
Duplicate Detection
   │
   ▼
Cover Extraction
   │
   ▼
Storage
   │
   ▼
Library Registration
```

## Metadata

Se utilizará Mutagen para extraer metadata.

Se analizarán:

- Título.
- Artista.
- Álbum.
- Album artist.
- Año.
- Género.
- Track number.
- Disc number.
- Duración.
- Artwork.
- ISRC cuando esté disponible.

## Detección de duplicados

Se utilizarán diferentes mecanismos:

- SHA256 del archivo.
- ISRC.
- Normalización de metadata.
- Artista.
- Título.
- Duración.
- Album.

La detección de duplicados no deberá eliminar automáticamente versiones diferentes de una canción.

---

# 10. Sistema de almacenamiento

El almacenamiento será independiente del resto de módulos.

## Storage abstraction

```python
class StorageProvider:
    async def upload(self, file, key):
        ...

    async def delete(self, key):
        ...

    async def get_stream_url(self, key):
        ...

    async def get_metadata(self, key):
        ...
```

## Provider inicial

Supabase Storage.

## Providers futuros

- Local filesystem.
- S3.
- Cloudflare R2.
- MinIO.
- Otros proveedores compatibles.

La aplicación deberá poder cambiar de proveedor sin modificar los módulos de biblioteca o reproducción.

Los archivos estarán almacenados en buckets privados.

El backend validará los permisos antes de generar URLs firmadas de duración limitada.

---

# 11. Reproductor

El reproductor será global y persistente.

No se reiniciará al cambiar de página.

## Funcionalidades

- Play.
- Pause.
- Previous.
- Next.
- Seek.
- Volume.
- Shuffle.
- Repeat.
- Queue.
- Add to queue.
- Play next.
- Remove from queue.
- Clear queue.
- Persistencia del estado.
- Reproducción en segundo plano cuando el navegador lo permita.
- Media Session API.
- Controles en pantalla de bloqueo compatibles.
- Controles Bluetooth compatibles.

## Arquitectura

El backend autoriza la reproducción y genera URLs temporales.

La reproducción normal no pasará por el backend de Render.

```text
Frontend Player
      │
      ▼
Backend Authorization
      │
      ▼
Signed URL
      │
      ▼
Private Storage
      │
      ▼
Audio Streaming
```

El reproductor deberá soportar:

- HTTP Range.
- Seek.
- Progressive playback.
- Buffering.
- Refresh de URLs expiradas.

---

# 12. Playlists

Los usuarios podrán crear playlists privadas.

## Funcionalidades

- Crear playlist.
- Eliminar playlist.
- Renombrar.
- Descripción.
- Añadir canciones.
- Eliminar canciones.
- Reordenar.
- Play.
- Shuffle.
- Añadir playlist a la cola.
- Portada personalizada.
- Importación de playlists.

## Visibilidad

```text
PRIVATE
SHARED
```

La visibilidad pública se podrá añadir en el futuro cuando tenga sentido.

---

# 13. Favoritos

Cada usuario tendrá sus propios favoritos.

Los favoritos serán independientes de las playlists.

Se podrán:

- Marcar canciones.
- Desmarcar canciones.
- Consultar favoritos.
- Reproducir favoritos.
- Añadir favoritos a playlists.

---

# 14. Búsqueda

La búsqueda será global dentro de la biblioteca del usuario.

Se podrá buscar por:

- Título.
- Artista.
- Album.
- Género.
- Metadata.

La búsqueda utilizará PostgreSQL Full Text Search y `pg_trgm` cuando resulte útil.

Se incluirá:

- Búsqueda fuzzy.
- Normalización.
- Resultados paginados.
- Filtros.
- Ordenación.

La búsqueda nunca devolverá recursos privados de otros usuarios.

---

# 15. Importación de playlists

La aplicación permitirá importar playlists externas.

## V1

### CSV

Será el sistema universal de importación.

Permitirá importar playlists con campos como:

- Title.
- Artist.
- Album.
- Duration.
- ISRC.
- Position.

### Spotify

Integración mediante OAuth y credenciales propias de la instancia o aplicación, dependiendo de las restricciones actuales del proveedor.

Se utilizará únicamente para obtener metadata y referencias de canciones.

### YouTube / YouTube Music

Integración mediante métodos autorizados y compatibles con las condiciones de uso de los proveedores.

No se descargará ni extraerá audio de Spotify, YouTube ni otros servicios.

---

# 16. Matching de canciones

Cuando se importe una playlist, las canciones deberán buscarse en la biblioteca del usuario.

## Matching cascade

```text
ISRC Exact Match
       │
       ▼
Normalized Artist + Title
       │
       ▼
Artist + Title + Duration
       │
       ▼
Album Matching
       │
       ▼
Fuzzy Matching
       │
       ▼
Manual Review
```

## Resultados

```text
EXACT
HIGH_CONFIDENCE
REVIEW_REQUIRED
UNMATCHED
DUPLICATE
INVALID
```

El sistema deberá detectar diferentes versiones:

- Live.
- Acoustic.
- Remastered.
- Remix.
- Radio Edit.
- Instrumental.
- Extended.
- Demo.

No se deberán eliminar automáticamente las diferencias entre versiones.

## Informe de importación

Después de importar una playlist, se mostrará:

- Canciones encontradas.
- Canciones no encontradas.
- Matches exactos.
- Matches aproximados.
- Canciones que necesitan revisión.
- Duplicados.
- Errores.

---

# 17. Compartición

En V1 se implementará una compartición controlada dentro de la instancia.

La amistad no será necesaria para compartir recursos.

## Recursos compartibles

- Playlists.
- Canciones.
- Álbumes.

## Permisos

```text
VIEW
PLAY
```

La compartición deberá ser explícita, revocable y independiente de la relación entre usuarios.

Ser amigo de alguien no dará acceso automático a su biblioteca.

---

# 18. Sistema de amigos — V1.5

Como primera aproximación a las funcionalidades sociales, se podrá implementar un sistema de amigos local.

Los usuarios pertenecerán a la misma instancia.

## Funcionalidades

- Buscar usuarios de la instancia.
- Enviar solicitud de amistad.
- Aceptar solicitud.
- Rechazar solicitud.
- Eliminar amigo.
- Bloquear usuario.
- Ver perfiles configurados como visibles.
- Compartir playlists.

Esta funcionalidad no será un requisito para tener una V1 funcional.

---

# 19. Sistema de amigos descentralizado — V2

La federación permitirá que usuarios pertenecientes a diferentes instancias puedan interactuar.

## Arquitectura

Cada instancia será independiente.

No existirá un servidor central obligatorio.

```text
┌─────────────────────┐
│ Instance A          │
│                    │
│ User: Andrés       │
│                    │
│ Database A         │
└─────────┬──────────┘
          │
          │ Secure Federation API
          │
          ▼
┌─────────────────────┐
│ Instance B          │
│                    │
│ User: Juan         │
│                    │
│ Database B         │
└─────────────────────┘
```

## Requisitos

- Remote identity.
- Instance discovery.
- Remote friend requests.
- Request acceptance.
- Friend removal.
- Blocking.
- Remote profile visibility.
- Remote playlist sharing.
- Authentication between instances.
- Signed requests.
- Replay protection.
- Rate limiting.
- Abuse protection.
- SSRF protection.
- Permission validation.
- Federation API.

## Principio de privacidad

La federación nunca dará acceso automáticamente a una biblioteca.

Cada recurso deberá comprobar sus permisos independientemente de la amistad.

---

# 20. Seguridad

La seguridad será uno de los pilares del proyecto.

## Authentication

- Hash de contraseñas mediante Argon2id.
- Sesiones seguras.
- Refresh token rotation.
- Revocación de sesiones.
- Rate limiting.
- Protección contra brute force.
- Password recovery seguro.

## Authorization

- RLS.
- Ownership validation.
- Instance membership validation.
- Resource permission checks.
- Deny by default.

## Secrets

Los siguientes elementos nunca se expondrán al frontend:

- Service role keys.
- OAuth secrets.
- Encryption keys.
- Internal secrets.

## OAuth

- State anti-CSRF.
- Validación de redirects.
- Scopes mínimos.
- Tokens cifrados.
- Rotación cuando corresponda.

## Storage

- Buckets privados.
- Signed URLs.
- TTL.
- Validación de permisos.
- No listar archivos privados.
- No registrar URLs firmadas.

## Uploads

- Validación de formatos.
- Validación de tamaño.
- Validación real del contenido.
- Metadata sanitizada.
- SHA256.
- Límites de procesamiento.
- No ejecutar archivos.
- Protección contra archivos maliciosos.

## SSRF

Las integraciones que acepten URLs deberán bloquear:

- Localhost.
- Redes privadas.
- Link-local.
- Servicios internos.
- Redirects peligrosos.

## Logs

Se evitará registrar:

- Contraseñas.
- Tokens.
- URLs firmadas.
- Credenciales.
- Metadata personal innecesaria.

---

# 21. Arquitectura técnica

## Estrategia

Se comenzará con un **Modular Monolith**.

No se utilizarán microservicios desde el inicio.

Los módulos tendrán:

- Interfaces.
- Contratos.
- Dependencias controladas.
- Responsabilidades claras.

Se podrán extraer servicios en el futuro si existe una necesidad real.

## Frontend

```text
SvelteKit
Svelte
TypeScript
PWA
```

## Backend

```text
Python
FastAPI
Pydantic
asyncio
SQLAlchemy
```

## Database

```text
PostgreSQL
```

## Storage

```text
Supabase Storage
```

## Authentication

```text
Supabase Auth
```

o una implementación propia compatible con la arquitectura de sesiones definida, según las necesidades finales de seguridad y control.

## Metadata

```text
Mutagen
```

## Audio processing

```text
FFmpeg
FFprobe
```

Solo se utilizarán cuando sea necesario.

## Deployment inicial

| Componente | Tecnología |
|---|---|
| Frontend | Vercel |
| Backend | Render |
| Database | Supabase PostgreSQL |
| Authentication | Supabase Auth / capa de autenticación |
| Storage | Supabase Storage |
| CI/CD | GitHub Actions |
| Repository | GitHub |

La arquitectura deberá ser capaz de evolucionar hacia un despliegue Docker self-hosted.

---

# 22. Arquitectura modular

```text
Personal Music Cloud
│
├── Identity
├── Instance Management
├── User Management
├── Authentication
├── Sessions
├── Library
├── Metadata
├── Storage
├── Playback
├── Playlists
├── Favorites
├── Search
├── Importers
├── Matching
├── Jobs
├── Sharing
├── Quota Management
├── Settings
├── Dashboard
├── Observability
│
├── Social [Future]
│   ├── Friends
│   ├── Profiles
│   └── Blocking
│
└── Federation [V2]
    ├── Remote Identity
    ├── Instance Discovery
    ├── Federation API
    ├── Remote Friends
    └── Remote Sharing
```

---

# 23. Jobs

Los procesos pesados no se ejecutarán directamente en peticiones HTTP.

Se utilizará un sistema persistente de jobs.

## Jobs

- Upload processing.
- Metadata extraction.
- Cover extraction.
- Duplicate detection.
- Playlist import.
- Matching.
- Storage operations.

## Estados

```text
PENDING
CLAIMED
RUNNING
COMPLETE
RETRY_WAIT
FAILED
CANCELLED
```

El sistema deberá soportar:

- Persistencia.
- Retry.
- Timeout.
- Cancelación.
- Progress.
- Recovery.
- Idempotency.
- Concurrency limits.

Inicialmente se podrá implementar sobre PostgreSQL.

---

# 24. Base de datos

## Core

```text
instances
instance_members
invitations
profiles
user_settings
user_sessions
```

## Library

```text
artists
albums
tracks
track_files
genres
track_genres
```

## User data

```text
playlists
playlist_tracks
favorites
listening_history
```

## Importers

```text
provider_connections
import_jobs
import_items
```

## Sharing

```text
sharing_permissions
```

## Future social

```text
friendships
user_blocks
```

## Future federation

```text
remote_users
remote_instances
federation_requests
```

---

# 25. Repository structure

```text
personal-music-cloud/
│
├── apps/
│   ├── web/
│   │   ├── routes/
│   │   ├── components/
│   │   ├── player/
│   │   ├── library/
│   │   ├── playlists/
│   │   ├── dashboard/
│   │   ├── admin/
│   │   └── social/
│   │
│   └── api/
│       ├── core/
│       ├── application/
│       ├── modules/
│       │   ├── identity/
│       │   ├── instances/
│       │   ├── users/
│       │   ├── authentication/
│       │   ├── sessions/
│       │   ├── library/
│       │   ├── metadata/
│       │   ├── storage/
│       │   ├── playback/
│       │   ├── playlists/
│       │   ├── favorites/
│       │   ├── search/
│       │   ├── importers/
│       │   ├── matching/
│       │   ├── jobs/
│       │   ├── sharing/
│       │   └── settings/
│       ├── infrastructure/
│       └── tests/
│
├── packages/
│   ├── shared-types/
│   ├── metadata/
│   ├── matching/
│   ├── importer-contracts/
│   └── storage-contracts/
│
├── supabase/
│   ├── migrations/
│   ├── seed.sql
│   └── config.toml
│
├── deployment/
│   ├── vercel/
│   ├── render/
│   └── docker/
│
├── docs/
│   ├── master-design.md
│   ├── architecture.md
│   ├── security.md
│   ├── multi-user.md
│   ├── sharing.md
│   ├── self-hosting.md
│   ├── storage.md
│   ├── spotify.md
│   ├── youtube.md
│   ├── backup-restore.md
│   ├── contributing.md
│   └── agent-guidelines.md
│
├── .github/
│   └── workflows/
│
├── AGENTS.md
├── SECURITY.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── CHANGELOG.md
└── .env.example
```

---

# 26. Roadmap

## Phase 0 — Foundation

- Crear repository.
- Definir monorepo.
- Configurar frontend y backend.
- Configurar CI.
- Definir arquitectura.
- Definir contratos.
- Documentación inicial.
- Threat model.
- Configuración de desarrollo.

## Phase 1 — Infrastructure & Identity

- PostgreSQL.
- Supabase.
- Authentication.
- Profiles.
- Instance.
- Owner bootstrap.
- Multi-user.
- Invitations.
- Roles.
- Account activation.
- Secure sessions.
- RLS.
- Security tests.

## Phase 2 — Library Core

- Artists.
- Albums.
- Tracks.
- Track files.
- Genres.
- Metadata normalization.
- Ownership.
- Deduplication.
- Search.
- Pagination.
- Library isolation.

## Phase 3 — Ingestion

- Upload.
- Validation.
- Persistent jobs.
- Metadata extraction.
- Cover extraction.
- Hashes.
- Duplicate detection.
- Storage.
- Retry.
- Cancellation.
- Progress.
- Quotas.

## Phase 4 — Playback

- Authorization.
- Signed URLs.
- Range requests.
- Seek.
- Progressive playback.
- URL refresh.
- Global player.
- Queue.
- Shuffle.
- Repeat.
- Persistence.
- iOS testing.

## Phase 5 — Playlists & Library UX

- Home.
- Songs.
- Artists.
- Albums.
- Genres.
- Favorites.
- Playlists.
- CRUD.
- Reordering.
- Queue.
- Drag and drop.
- Responsive UI.

## Phase 6 — Search & Matching

- Full Text Search.
- pg_trgm.
- Fuzzy search.
- Filters.
- Confidence scoring.
- Version detection.
- Matching benchmarks.

## Phase 7 — Importers

- CSV.
- Spotify.
- YouTube / YouTube Music, if supported through compliant integrations.
- Provider contracts.
- Matching.
- Import reports.

## Phase 8 — PWA & Mobile

- Manifest.
- Installation.
- Icons.
- Responsive design.
- Offline app shell.
- Media Session.
- Lock screen.
- Background playback.
- Bluetooth.
- iOS testing.
- Cache isolation.
- Download manager future.

## Phase 9 — Release V1

- Self-hosting documentation.
- Configuration.
- Backup and restore.
- Security review.
- Deployment.
- Testing.
- Contribution guidelines.
- Release.
- Open source publication.

## Phase 10 — V1.5 Social

- Local friends.
- Friend requests.
- Accept/reject.
- Remove friends.
- Blocking.
- Profiles.
- Shared playlists.
- Privacy settings.

## Phase 11 — V2 Federation

- Remote identity.
- Instance discovery.
- Federation API.
- Remote friend requests.
- Authentication between instances.
- Signed requests.
- Replay protection.
- Rate limiting.
- Remote sharing.
- Abuse protection.
- Federation security tests.

---

# 27. MVP priorities

## Must have

- Owner.
- Multi-user.
- Invite-only users.
- Account activation.
- Secure passwords.
- Sessions.
- Profile selector.
- Private libraries.
- Upload.
- Metadata.
- Covers.
- Duplicate detection.
- Search.
- Playback.
- Seek.
- Queue.
- Shuffle.
- Repeat.
- Playlists.
- Favorites.
- Dashboard.
- CSV import.
- Matching.
- PWA.
- Mobile support.
- Backup.
- Restore.
- Security.
- Self-hosting documentation.

## Nice to have

- Local friends.
- Shared playlists.
- Listening statistics.
- Advanced dashboard customization.
- Spotify import, subject to API availability and restrictions.
- Additional metadata enrichment.
- Advanced matching.

## Out of scope for V1

- Decentralized friends.
- Federation.
- Remote instance discovery.
- Distributed identity.
- Social network.
- Recommendations.
- Wrapped-style yearly statistics.
- Native mobile apps.
- Advanced offline music downloads.
- Equalizer.
- Lyrics.
- Plugin ecosystem.
- Microservices.
- One-click Docker deployment.

---

# 28. Agent architecture

El desarrollo podrá distribuirse entre agentes especializados.

## Agent 0 — Architect

- Arquitectura.
- Contracts.
- Module boundaries.
- Technical decisions.
- Integration.
- Code review.
- Architectural consistency.

## Agent 1 — Backend Core

- FastAPI.
- Application layer.
- DI.
- API.
- Error handling.
- Authentication integration.

## Agent 2 — Database & Security

- Schema.
- Migrations.
- RLS.
- Ownership.
- Tenant isolation.
- Storage policies.
- Security tests.

## Agent 3 — Frontend & UX

- SvelteKit.
- UI.
- Navigation.
- Library.
- Playlist.
- Dashboard.
- Admin.
- Responsive design.

## Agent 4 — Player

- Audio engine.
- Player state.
- Queue.
- Media Session.
- Seek.
- Mobile testing.

## Agent 5 — Library & Metadata

- Metadata extraction.
- Mutagen.
- Normalization.
- Deduplication.
- Validation.
- Upload processing.

## Agent 6 — Importers & Matching

- CSV.
- Spotify.
- YouTube integrations.
- Contracts.
- Matching.
- Confidence scoring.
- Reports.

## Agent 7 — QA & Security

- Unit tests.
- Integration tests.
- Contract tests.
- E2E.
- Security.
- Performance.
- Regression.

---

# 29. Agent guidelines

Todos los agentes deberán:

- Leer la documentación de arquitectura antes de trabajar.
- Inspeccionar el código y los contratos existentes.
- Reutilizar interfaces.
- Identificar límites de módulos.
- No duplicar abstracciones.
- No saltarse las capas de arquitectura.
- No introducir dependencias innecesarias.
- No modificar módulos ajenos sin autorización.
- No realizar refactors no relacionados.
- No exponer secretos.
- No debilitar la autenticación.
- No saltarse RLS.
- No confiar en validaciones del frontend.
- No confiar en IDs de ownership proporcionados por el cliente.
- No descargar audio de Spotify o YouTube.
- Mantener providers sustituibles.
- Ejecutar tests, lint y typecheck.
- Documentar cambios.

## Definition of Done

Una tarea estará terminada cuando:

- La implementación esté completa.
- Los tests estén implementados y pasen.
- Lint pase.
- Typecheck pase.
- La seguridad haya sido revisada.
- La arquitectura se mantenga.
- La documentación esté actualizada.
- Los criterios de aceptación se cumplan.

## Agent report

Cada agente deberá entregar:

- Summary.
- Files changed.
- Tests.
- Results.
- Issues.
- Decisions.
- Blockers.

---

# 30. Filosofía de desarrollo

El proyecto no debe intentar competir con Spotify en cantidad de funcionalidades desde el primer día.

La prioridad es construir una plataforma que:

1. Funcione.
2. Sea estable.
3. Sea segura.
4. Sea fácil de utilizar.
5. Ofrezca una buena experiencia de reproducción.
6. Permita que cada usuario gestione su propia música.
7. Sea fácil de instalar y administrar.
8. Tenga una arquitectura preparada para crecer.

La descentralización social es una visión de futuro, no un requisito para lanzar la primera versión.

Primero se construirá una plataforma musical que pueda utilizarse diariamente por el propietario, su familia y sus amigos.

Después, cuando la base sea sólida, Personal Music Cloud podrá evolucionar hacia una red musical federada donde cada usuario mantenga el control de su propia instancia y su propia música.

---

# Objetivo final

**Personal Music Cloud debe permitir que cualquier persona tenga su propio servicio de música, alojado por ella misma, con su biblioteca, sus playlists, sus usuarios y sus reglas, sin depender de una plataforma centralizada.**

La primera versión será una solución personal y familiar.

La segunda versión permitirá conectar esas soluciones independientes y convertirlas en una red social musical descentralizada.

**V1: Tu música, para ti y los tuyos.**

**V2: Tu música, conectada con el mundo.**
