<script>
  export let playbackQueue;
  export let currentTrack;
  export let playerVisible;
  export let onClose;
  export let onPlayTrack;
  export let onRemove;
</script>

<aside class="queue-panel" class:player-visible={playerVisible} aria-label="Cola de reproducción">
  <div class="queue-heading">
    <strong>Cola de reproducción</strong>
    <span>{playbackQueue.length} canciones</span>
    <button onclick={onClose} aria-label="Cerrar cola">×</button>
  </div>
  {#if currentTrack}
    <div class="queue-current"><small>Reproduciendo</small><strong>{currentTrack.title}</strong></div>
  {/if}
  {#each playbackQueue.filter((track) => track.id !== currentTrack?.id) as track}
    <article>
      <button onclick={() => onPlayTrack(track)}>
        <strong>{track.title}</strong>
        <span>{track.artist || "Artista desconocido"}</span>
      </button>
      <button onclick={() => onRemove(track.id)} aria-label={`Quitar ${track.title} de la cola`}>×</button>
    </article>
  {:else}
    <p>No hay canciones próximas en la cola.</p>
  {/each}
</aside>
