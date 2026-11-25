<script>
  import { assetUrl, formatTime, hideBrokenImage, text } from "../lib/format.js";

  export let currentTrack;
  export let isPlaying;
  export let shuffleMode;
  export let loopMode;
  export let showQueuePanel;
  export let queueLength;
  export let progress;
  export let duration;
  export let volume;
  export let onToggleShuffle;
  export let onPrevious;
  export let onTogglePlayback;
  export let onNext;
  export let onToggleQueue;
  export let onCycleLoop;
  export let onSeek;
  export let onVolume;
</script>

<!-- The <audio> element stays owned by App.svelte (playback, Media Session and devices use it) and is slotted in here. -->
<footer class="player">
  <div class="now-playing">
    <div class="mini-cover">
      {#if currentTrack.cover_url}
        <img src={assetUrl(currentTrack.cover_url)} alt="" onerror={hideBrokenImage} />
      {:else}
        ♫
      {/if}
    </div>
    <div><strong>{text(currentTrack.title, "Canción sin título")}</strong><span>{text(currentTrack.artist, "Artista desconocido")}</span></div>
  </div>
  <div class="player-center">
    <div class="player-controls">
      <button class:active={shuffleMode} onclick={onToggleShuffle} aria-label="Aleatorio" title="Aleatorio">⇄</button>
      <button onclick={onPrevious} aria-label="Anterior" title="Anterior">↤</button>
      <button class="player-toggle" onclick={onTogglePlayback}>{isPlaying ? "Ⅱ" : "▶"}</button>
      <button onclick={onNext} aria-label="Siguiente" title="Siguiente">↦</button>
      <button class:active={showQueuePanel} onclick={onToggleQueue} aria-label={`Cola de reproducción (${queueLength})`} title="Cola de reproducción">≡</button>
      <button class:active={loopMode !== "off"} onclick={onCycleLoop} aria-label="Modo bucle" title={loopMode === "off" ? "Bucle desactivado" : loopMode === "all" ? "Repetir lista" : "Repetir canción"}>
        {loopMode === "one" ? "↻1" : "↻"}
      </button>
    </div>
    <div class="timeline">
      <span>{formatTime(progress)}</span>
      <input aria-label="Posición" type="range" min="0" max={duration || 0} value={progress} oninput={onSeek} />
      <span>{formatTime(duration)}</span>
    </div>
  </div>
  <input class="volume" aria-label="Volumen" type="range" min="0" max="1" step="0.05" value={volume} oninput={onVolume} />
  <slot />
</footer>
