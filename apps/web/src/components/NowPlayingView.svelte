<script>
  import { onMount } from "svelte";
  import { assetUrl, formatTime, hideBrokenImage, text } from "../lib/format.js";

  export let currentTrack;
  export let isPlaying;
  export let progress = 0;
  export let duration = 0;
  export let volume = 0.8;
  export let shuffleMode = false;
  export let loopMode = "off";
  export let favorite = false;
  export let queueLength = 0;
  export let onClose;
  export let onTogglePlayback;
  export let onPrevious;
  export let onNext;
  export let onToggleShuffle;
  export let onCycleLoop;
  export let onSeek;
  export let onVolume;
  export let onToggleQueue;
  export let onToggleFavorite;
  export let onOpenArtist;

  let dragOffset = 0;
  let dragStart = null;
  let sheet;

  // Listeners are attached outside the template: the sheet is a container, not a
  // control, and Svelte asks for an interactive role on elements with touch handlers.
  onMount(() => {
    if (!sheet) return;
    sheet.addEventListener("touchstart", startDrag, { passive: true });
    sheet.addEventListener("touchmove", moveDrag, { passive: true });
    sheet.addEventListener("touchend", endDrag);
    return () => {
      sheet.removeEventListener("touchstart", startDrag);
      sheet.removeEventListener("touchmove", moveDrag);
      sheet.removeEventListener("touchend", endDrag);
    };
  });

  $: artist = text(currentTrack?.artist, "Artista desconocido");
  $: title = text(currentTrack?.title, "Canción sin título");
  $: album = text(currentTrack?.album, "Auralith");
  $: remaining = Math.max(0, (Number(duration) || 0) - (Number(progress) || 0));

  function handleKeydown(event) {
    if (event.key === "Escape") onClose();
  }

  function startDrag(event) {
    if (event.touches.length !== 1) return;
    if (event.target.closest("input")) return;
    dragStart = event.touches[0].clientY;
    dragOffset = 0;
  }

  function moveDrag(event) {
    if (dragStart === null || event.touches.length !== 1) return;
    dragOffset = Math.max(0, Math.min(event.touches[0].clientY - dragStart, 220));
  }

  function endDrag() {
    if (dragStart === null) return;
    dragStart = null;
    if (dragOffset > 120) {
      dragOffset = 0;
      onClose();
      return;
    }
    dragOffset = 0;
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="now-playing-view" role="dialog" aria-modal="true" aria-label={`Reproduciendo ${title}`}>
  <div class="np-backdrop" aria-hidden="true">
    {#if currentTrack?.cover_url}
      <img src={assetUrl(currentTrack.cover_url)} alt="" />
    {/if}
  </div>
  <div
    class="np-sheet"
    bind:this={sheet}
    style={`transform: translateY(${dragOffset}px); transition: ${dragStart === null ? "" : "none"}`}
  >
    <header class="np-top">
      <button class="np-icon" onclick={onClose} aria-label="Cerrar reproductor" title="Cerrar">⌄</button>
      <div class="np-context">
        <small>Reproduciendo</small>
        <strong>{album}</strong>
      </div>
      <button class="np-icon" onclick={onToggleQueue} aria-label={`Cola de reproducción (${queueLength})`} title="Cola de reproducción">≡</button>
    </header>

    <section class="np-stage">
      <div class="np-cover">
        {#if currentTrack?.cover_url}
          <img src={assetUrl(currentTrack.cover_url)} alt={`Portada de ${album}`} onerror={hideBrokenImage} />
        {:else}
          <span>♫</span>
        {/if}
      </div>

      <div class="np-meta">
        <div class="np-titles">
          <h2>{title}</h2>
          <button class="np-artist" onclick={onOpenArtist} title={`Ver ${artist}`}>{artist}</button>
        </div>
        <button
          class="np-favorite"
          class:active={favorite}
          onclick={onToggleFavorite}
          aria-pressed={favorite}
          aria-label={favorite ? "Quitar de favoritos" : "Añadir a favoritos"}
          title={favorite ? "Quitar de favoritos" : "Añadir a favoritos"}
        >{favorite ? "✓" : "♡"}</button>
      </div>

      <div class="np-timeline">
        <input
          aria-label="Posición de la canción"
          type="range"
          min="0"
          max={Number(duration) || 0}
          step="0.1"
          value={progress}
          oninput={onSeek}
        />
        <div><span>{formatTime(progress)}</span><span>-{formatTime(remaining)}</span></div>
      </div>

      <div class="np-controls">
        <button class="np-control" class:active={shuffleMode} onclick={onToggleShuffle} aria-label="Aleatorio" title="Aleatorio">⇄</button>
        <button class="np-control np-skip" onclick={onPrevious} aria-label="Anterior" title="Anterior">⏮</button>
        <button class="np-play" onclick={onTogglePlayback} aria-label={isPlaying ? "Pausar" : "Reproducir"} title={isPlaying ? "Pausar" : "Reproducir"}>
          {isPlaying ? "Ⅱ" : "▶"}
        </button>
        <button class="np-control np-skip" onclick={onNext} aria-label="Siguiente" title="Siguiente">⏭</button>
        <button
          class="np-control"
          class:active={loopMode !== "off"}
          onclick={onCycleLoop}
          aria-label="Modo bucle"
          title={loopMode === "off" ? "Bucle desactivado" : loopMode === "all" ? "Repetir lista" : "Repetir canción"}
        >{loopMode === "one" ? "↻1" : "↻"}</button>
      </div>

      {#if Number.isFinite(volume)}
        <div class="np-utility">
          <label class="np-volume">
            <span aria-hidden="true">Vol</span>
            <input aria-label="Volumen" type="range" min="0" max="1" step="0.05" value={volume} oninput={onVolume} />
          </label>
        </div>
      {/if}

      <button class="np-artist-card" onclick={onOpenArtist}>
        <span class="np-artist-art">
          {#if currentTrack?.cover_url}
            <img src={assetUrl(currentTrack.cover_url)} alt="" />
          {:else}
            ♫
          {/if}
        </span>
        <span class="np-artist-text">
          <small>Información sobre el artista</small>
          <strong>{artist}</strong>
        </span>
        <span class="np-chevron" aria-hidden="true">›</span>
      </button>
    </section>
  </div>
</div>
