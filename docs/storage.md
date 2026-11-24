# Arquitectura de Almacenamiento y Nube en AURALITH

Este documento detalla la abstracción de almacenamiento, los proveedores soportados en el MVP y la integración de almacenamiento en la nube secundaria (Google Drive / Dropbox) como tier frío.

---

## 1. Principio de desacoplamiento

El sistema de almacenamiento en Auralith está completamente desacoplado de la lógica de catálogo, base de datos y reproducción. La interfaz `StorageProvider` (`apps/api/infrastructure/storage/interface.py`) define el contrato estándar:

```python
class StorageProvider(Protocol):
    def upload(self, key: str, content: bytes, content_type: str) -> str: ...
    def open(self, key: str, start: int | None = None, end: int | None = None) -> BinaryIO: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
    def size(self, key: str) -> int: ...
```

---

## 2. Proveedores del MVP

El MVP incluye tres proveedores principales configurables mediante variables de entorno:

### 2.1. Disco Local (`local`)
- **Variable:** `AURALITH_STORAGE_PROVIDER=local`
- **Uso:** Adecuado para despliegues con Docker Compose, almacenamiento en volumen local o NAS montado en sistema de archivos.
- **Ruta:** Configurable con `AURALITH_STORAGE_DIR` (por defecto `./data/music`).
- **Soporte de rangos:** Lectura directa mediante seek sobre archivos en disco.

### 2.2. Supabase Storage (`supabase`)
- **Variable:** `AURALITH_STORAGE_PROVIDER=supabase`
- **Variables requeridas:**
  - `SUPABASE_URL`: URL HTTPS de la instancia de Supabase.
  - `SUPABASE_SECRET_KEY`: Service role secret key (nunca expuesta al frontend).
  - `SUPABASE_STORAGE_BUCKET`: Nombre del bucket privado (por defecto `music`).
- **Seguridad:** Bucket privado protegido mediante RLS. La API backend autentica cada petición antes de solicitar el flujo con cabeceras de rango al API REST de Supabase.

### 2.3. S3 / Neon Object Storage (`neon`)
- **Variable:** `AURALITH_STORAGE_PROVIDER=neon`
- **Variables soportadas:**
  - `NEON_URL` / `AWS_ENDPOINT_URL_S3`: Endpoint S3 compatible.
  - `NEON_STORAGE_BUCKET` / `AWS_BUCKET_NAME`: Nombre del bucket (`music`).
  - `NEON_ACCESS_KEY_ID` / `AWS_ACCESS_KEY_ID`.
  - `NEON_SECRET_ACCESS_KEY` / `AWS_SECRET_ACCESS_KEY`.
- **Soporte de rangos:** Solicitudes `Range` nativas mediante el cliente S3 (boto3) con reintentos exponenciales ante fallos transitorios.

---

## 3. Almacenamiento en Nubes Secundarias: Google Drive y Dropbox

### 3.1. Rol en la arquitectura: Tier Frío (Cold Storage)
Google Drive y Dropbox **no son proveedores de streaming primario** en el MVP por razones de diseño y estabilidad:
1. **Límites de cuota agresivos:** Las APIs de Google Drive y Dropbox imponen cuotas estrictas de peticiones por minuto y límites de descarga diaria que pueden bloquear la reproducción continua.
2. **Falta de soporte robusto para HTTP Range:** Las APIs de archivos en la nube de consumo no ofrecen garantías de latencia baja ni seek rápido de paquetes de audio necesarios para buffering progresivo.
3. **Dependencia de tokens de usuario:** Requieren flujos interactivos de OAuth2 y revocación periódica de tokens.

Por tanto, Drive y Dropbox se conciben como **almacenamiento secundario / frío opcional**:
- La biblioteca y los metadatos residen en la base de datos principal de Auralith.
- Las pistas raramente reproducidas o bibliotecas masivas pueden residir en la nube del usuario (Google Drive o Dropbox).
- **Recuperación bajo demanda:** Al solicitar la reproducción, el backend descarga el archivo a una **caché local temporal acotada** (LRU con tamaño máximo configurable) desde la que se realiza el streaming progresivo.
- Si el archivo ya está en caché local, la reproducción es instantánea; si no, se produce una breve espera de descarga inicial.

```text
┌─────────────────┐       Solicitud stream       ┌──────────────────┐
│  Reproductor    │ ───────────────────────────> │  API Auralith    │
└─────────────────┘                              └─────────┬────────┘
                                                           │
                                             ¿En caché?    │
                                            ┌──────────────┴──────────────┐
                                            │ SÍ                          │ NO
                                            ▼                             ▼
                                   ┌─────────────────┐           ┌──────────────────┐
                                   │  Caché local    │           │  Google Drive /  │
                                   │  (Streaming)    │           │  Dropbox (OAuth) │
                                   └─────────────────┘           └────────┬─────────┘
                                                                          │ Descarga
                                                                          ▼
                                                                 ┌──────────────────┐
                                                                 │  Almacena en     │
                                                                 │  caché local     │
                                                                 └──────────────────┘
```

### 3.2. Requisitos de seguridad para la integración futura
1. **Flujo OAuth2 con PKCE:** El propietario de la instancia conecta su cuenta de Google o Dropbox de forma consentida en el panel de administración.
2. **Cifrado de Tokens:** Los refresh tokens se almacenan cifrados en la base de datos de la instancia mediante claves derivadas en el servidor. Nunca se transfieren al cliente/frontend.
3. **Aislamiento de ámbito (Scopes mínimos):** Solo se solicita acceso al directorio exclusivo de la aplicación (`drive.file` en Google Drive, `app_folder` en Dropbox).
4. **Validación de tipos de archivo:** Solo se procesan archivos de audio autorizados (MP3/FLAC) verificando firmas binarias e integridad SHA-256.
