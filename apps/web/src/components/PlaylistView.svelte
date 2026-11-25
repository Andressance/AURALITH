<script>
  import { assetUrl, hideBrokenImage, text } from "../lib/format.js";

  export let selectedPlaylist;
  export let currentTrack;
  export let isPlaying;
  export let onUploadCover;
  export let onShare;
  export let onToggleLibrary;
  export let onPlayTrack;
  export let onEnqueue;
  export let onRemove;
  export let onDragStart;
  export let onDragEnd;
</script>

<section class="playlist-hero">
  <div class="hero-cover">
    {#if selectedPlaylist.cover_url}
      <img src={assetUrl(selectedPlaylist.cover_url)} alt="" fetchpriority="low" loading="lazy" decoding="async" onerror={hideBrokenImage} />
    {:else}
      ♫
    {/if}
    {#if selectedPlaylist.role === "owner"}
      <label title="Cambiar foto">✎<input type="file" accept="image/jpeg,image/png,image/webp" onchange={onUploadCover} /></label>
    {/if}
  </div>
  <div>
    <span>{selectedPlaylist.role === "owner" ? "Playlist" : selectedPlaylist.role === "editor" ? "Colaboras en esta playlist" : "Compartida contigo"}</span>
    <h2>{selectedPlaylist.name}</h2>
    <p>{selectedPlaylist.shared ? `De ${selectedPlaylist.owner}` : "Auralith"} · {selectedPlaylist.tracks.length} canciones</p>
    <div class="hero-actions">
      {#if selectedPlaylist.role === "owner"}
        <button class="share-playlist" onclick={onShare}>Compartir</button>
      {:else}
        <button class="share-playlist" onclick={() => onToggleLibrary(selectedPlaylist)}>
          {selectedPlaylist.saved ? "Quitar de mi biblioteca" : "Añadir a mi biblioteca"}
        </button>
      {/if}
    </div>
  </div>
</section>
<section class="track-list playlist-tracks">
  {#each selectedPlaylist.tracks as track, index}
    <article
      class:playing={currentTrack?.id === track.id}
      draggable="true"
      ondragstart={(event) => onDragStart(event, track.id)}
      ondragend={onDragEnd}
    >
      <span class="track-index">{index + 1}</span>
      <button class="track-play" onclick={() => onPlayTrack(track)}>{currentTrack?.id === track.id && isPlaying ? "Ⅱ" : "▶"}</button>
      <div><strong>{text(track.title, "Canción sin título")}</strong><span>{text(track.artist, "Artista desconocido")}</span></div>
      <button class="row-action" onclick={() => onEnqueue(track, true)} title="Reproducir después" aria-label="Reproducir después">⏭</button>
      <button class="row-action" onclick={() => onEnqueue(track)} title="Añadir a la cola" aria-label="Añadir a la cola">＋</button>
      {#if selectedPlaylist.role !== "viewer"}
        <button class="row-action" onclick={() => onRemove(track)} title="Quitar">×</button>
      {/if}
    </article>
  {/each}
</section>
