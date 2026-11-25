<script>
  import { assetUrl, hideBrokenImage, text, titleInitial } from "../lib/format.js";

  export let visibleTracks;
  export let currentTrack;
  export let isPlaying;
  export let selectedTrackIds;
  export let uploading;
  export let onUpload;
  export let onPlayTrack;
  export let onEnqueue;
  export let onOpenPlaylistPicker;
  export let onFavorite;
  export let onDelete;
  export let onToggleSelection;
  export let onDragStart;
  export let onDragEnd;
</script>

<section class="library-header">
  <div><span>Tu música</span><h2>Made for you</h2></div>
  <label class="primary-upload" class:disabled={uploading}>Subir canciones<input type="file" multiple accept=".mp3,.flac,audio/mpeg,audio/flac" onchange={onUpload} disabled={uploading} /></label>
</section>
<section class="track-grid">
  {#each visibleTracks as track}
    <article
      class:playing={currentTrack?.id === track.id}
      draggable="true"
      ondragstart={(event) => onDragStart(event, track.id)}
      ondragend={onDragEnd}
    >
      <label class="track-select">
        <input
          type="checkbox"
          checked={selectedTrackIds.includes(track.id)}
          onchange={() => onToggleSelection(track.id)}
          aria-label={`Seleccionar ${text(track.title, "Canción")}`}
        />
      </label>
      <button class="cover" onclick={() => onPlayTrack(track)} aria-label={`Reproducir ${text(track.title, "Canción sin título")}`}>
        {#if track.cover_url}
          <img src={assetUrl(track.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
        {:else}
          <span>{titleInitial(track.title)}</span>
        {/if}
        <b>{currentTrack?.id === track.id && isPlaying ? "Ⅱ" : "▶"}</b>
      </button>
      <strong>{text(track.title, "Canción sin título")}</strong>
      <span>{text(track.artist, "Artista desconocido")}</span>
      <div class="track-actions">
        <button onclick={() => onEnqueue(track, true)} aria-label="Reproducir después" title="Reproducir después">⏭</button>
        <button onclick={() => onEnqueue(track)} aria-label="Añadir a la cola" title="Añadir a la cola">↗</button>
        <button onclick={() => onOpenPlaylistPicker(track.id)} aria-label="Añadir a playlist" title="Añadir a playlist">＋</button>
        <button onclick={() => onFavorite(track)} aria-label="Favorito" title="Favorito">♥</button>
        <button onclick={() => onDelete(track)} aria-label="Eliminar" title="Eliminar">×</button>
      </div>
    </article>
  {/each}
</section>
