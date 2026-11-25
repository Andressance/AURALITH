<script>
  export let devices;
  export let connected;
  export let deviceId;
  export let remoteTargetId;
  export let playerVisible;
  export let onClose;
  export let onToggleRemoteTarget;
  export let onTakeOver;
  export let onControl;
</script>

<aside class="queue-panel devices-panel" class:player-visible={playerVisible} aria-label="Dispositivos">
  <div class="queue-heading">
    <strong>Dispositivos</strong>
    <span>{devices.length} conectado(s)</span>
    <button onclick={onClose} aria-label="Cerrar dispositivos">×</button>
  </div>
  <p>Mismo perfil, otros dispositivos. Elige cuál controlas o pásale la reproducción.</p>
  {#if !connected}
    <p>Conectando con tus dispositivos…</p>
  {/if}
  {#each devices as device (device.device_id)}
    {@const self = device.device_id === deviceId}
    <article class="device-card" class:controlling={remoteTargetId === device.device_id}>
      <div class="device-info">
        <strong>{device.name}{self ? " · este dispositivo" : ""}</strong>
        <span>{device.track ? `${device.is_playing ? "Sonando" : "En pausa"}: ${device.track.title}` : "Sin reproducción"}</span>
      </div>
      {#if !self}
        <div class="device-actions">
          <button onclick={() => onToggleRemoteTarget(device)}>{remoteTargetId === device.device_id ? "Dejar de controlar" : "Controlar"}</button>
          {#if device.track}<button onclick={() => onTakeOver(device)}>Pasar aquí</button>{/if}
        </div>
      {/if}
    </article>
  {/each}
  {#if connected && devices.length < 2}
    <p class="jam-empty">Abre Auralith con esta cuenta en otro dispositivo y aparecerá aquí.</p>
  {/if}
  {#each devices.filter((device) => device.device_id === remoteTargetId) as target (target.device_id)}
    <div class="device-remote">
      <small>Controlando: {target.name}</small>
      <div class="jam-controls">
        <button onclick={() => onControl("prev")} aria-label="Anterior">⏮</button>
        <button onclick={() => onControl(target.is_playing ? "pause" : "play")}>{target.is_playing ? "Ⅱ Pausar" : "▶ Reproducir"}</button>
        <button onclick={() => onControl("next")} aria-label="Siguiente">⏭</button>
      </div>
    </div>
  {/each}
</aside>
