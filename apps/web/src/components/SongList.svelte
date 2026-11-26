<script>
  import { assetUrl, formatTime, hideBrokenImage, text, titleInitial } from "../lib/format.js";

  export let tracks = [];
  export let currentTrack;
  export let isPlaying;
  export let onPlayTrack;
  export let onEnqueue;
  export let showAlbum = true;
</script>

<div class="song-list">
  {#each tracks as track, index (track.id)}
    <article class:playing={currentTrack?.id === track.id}>
      <span class="song-index">{currentTrack?.id === track.id && isPlaying ? "Ⅱ" : index + 1}</span>
      <button
        class="song-cover"
        onclick={() => onPlayTrack(track)}
        aria-label={`Reproducir ${text(track.title, "Canción sin título")}`}
      >
        {#if track.cover_url}
          <img src={assetUrl(track.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
        {:else}
          <span>{titleInitial(track.title)}</span>
        {/if}
      </button>
      <button class="song-title" onclick={() => onPlayTrack(track)}>
        <strong>{text(track.title, "Canción sin título")}</strong>
        {#if showAlbum}
          <small>{text(track.album, "Sin álbum")}</small>
        {/if}
      </button>
      <span class="song-duration">{formatTime(track.duration)}</span>
      <button
        class="song-action"
        onclick={() => onEnqueue(track)}
        aria-label={`Añadir ${text(track.title, "canción")} a la cola`}
        title="Añadir a la cola"
      >＋</button>
    </article>
  {/each}
</div>
