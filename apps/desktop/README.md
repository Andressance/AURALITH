# Auralith Desktop

Aplicacion Electron ligera para Windows.

- Abre Auralith como una ventana de escritorio.
- Sincroniza la reproduccion con Discord Rich Presence.
- Requiere Discord Desktop abierto en Windows.

## Discord

1. Crea una aplicacion en el Discord Developer Portal.
2. Copia su Application ID.
3. Opcionalmente añade las imagenes `auralith`, `playing` y `paused` en Rich Presence Art Assets.
4. Ejecuta:

```powershell
$env:AURALITH_URL="http://localhost:8080"
$env:DISCORD_APPLICATION_ID="<application-id>"
npm.cmd start
```

## Instalar y ejecutar

```powershell
cd apps/desktop
npm.cmd install
npm.cmd start
```

## Crear instalador

```powershell
npm.cmd run build:win
```
