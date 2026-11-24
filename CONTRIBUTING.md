# Guía de Contribución / Contributing Guide

**Idioma / Language:** [Español](#espanol) · [English](#english)

---

<a id="espanol"></a>
## Español

¡Gracias por tu interés en contribuir a Auralith! Auralith es un proyecto autoalojado de código abierto, diseñado para ser ligero, seguro y modular.

### 1. Principios del proyecto
Antes de abrir una Issue o Pull Request, ten en cuenta las directrices del proyecto:
* **Foco en el alcance actual:** Consulta el [README.md](README.md) para conocer qué corresponde al MVP actual (V1) y qué pertenece a fases futuras (V1.5 y V2).
* **Seguridad y privacidad primero:** No introduzcas dependencias innecesarias, no debilites las comprobaciones de autorización en el backend y nunca confíes en validaciones exclusivas del cliente.
* **Proveedores intercambiables:** Mantén la independencia entre la lógica central y los proveedores de base de datos o almacenamiento (`StorageProvider`).

### 2. Flujo de trabajo para contribuir
1. Haz un fork del repositorio y crea una rama descriptiva para tu cambio:
   ```bash
   git checkout -b feature/nombre-de-la-mejora
   ```
2. Realiza tus cambios manteniendo el estilo de código existente.
3. Asegúrate de que todos los tests pasen y que la aplicación web compile:
   ```bash
   python -m pytest
   npm --prefix apps/web run build
   ```
4. Si añades nuevas rutas o funcionalidades críticas, añade tests unitarios o de integración en `tests/`.
5. Envía tu Pull Request con una descripción clara de los cambios y el motivo.

### 3. Reporte de vulnerabilidades
Si detectas una vulnerabilidad de seguridad, no abras una Issue pública. Por favor, revisa las instrucciones en [SECURITY.md](SECURITY.md) para reportarlo de forma privada y responsable.

---

<a id="english"></a>
## English

Thank you for your interest in contributing to Auralith! Auralith is a self-hosted, open-source music streaming platform designed to be lightweight, secure, and modular.

### 1. Project Principles
Before opening an Issue or Pull Request, please keep these core guidelines in mind:
* **Scope awareness:** Review [README.md](README.md) to understand what belongs to the current MVP (V1) versus future phases (V1.5 and V2).
* **Security and privacy first:** Avoid introducing unnecessary dependencies, never bypass server-side authorization checks, and do not trust client-supplied input.
* **Pluggable providers:** Keep core business logic decoupled from storage and database adapters (`StorageProvider`).

### 2. Contribution Workflow
1. Fork the repository and create a descriptive branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes adhering to the existing coding style and architecture.
3. Verify that the complete test suite passes and the web application builds cleanly:
   ```bash
   python -m pytest
   npm --prefix apps/web run build
   ```
4. If you introduce new endpoints or core behavior, include corresponding tests under `tests/`.
5. Submit your Pull Request detailing the changes, context, and motivation.

### 3. Reporting Security Issues
If you discover a security vulnerability, please do not open a public issue. Follow the instructions in [SECURITY.md](SECURITY.md) to report it privately.
