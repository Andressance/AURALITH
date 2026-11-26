<script>
  import { assetUrl, formatTime, hideBrokenImage, text, titleInitial } from "../lib/format.js";

  export let results = { artists: [], albums: [], tracks: [] };
  export let currentTrack;
  export let isPlaying;
  export let onPlayTrack;
  export let onPlayCollection;
  export let onEnqueue;
  export let onOpenArtist;

  $: total = results.artists.length + results.albums.length + results.tracks.length;
</script>

{#if !total}
  <p class="search-empty">No hay artistas, álbumes ni canciones que coincidan con tu búsqueda.</p>
{:else}
  <div class="search-results">
    {#if results.artists.length}
      <section class="search-section">
        <h3>Artistas</h3>
        <div class="artist-chips">
          {#each results.artists as artist (artist.key)}
            <button class="artist-chip" onclick={() => onOpenArtist(artist.name)}>
              <span class="artist-chip-art">
                {#if artist.cover_url}
                  <img src={assetUrl(artist.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
                {:else}
                  {titleInitial(artist.name)}
                {/if}
              </span>
              <span>
                <strong>{artist.name}</strong>
                <small>{artist.tracks.length} canciones · {artist.albums.length} álbumes</small>
              </span>
            </button>
          {/each}
        </div>
      </section>
    {/if}

    {#if results.albums.length}
      <section class="search-section">
        <h3>Álbumes</h3>
        <div class="album-grid">
          {#each results.albums as album (album.key)}
            <article class="album-card">
              <button
                class="album-card-cover"
                onclick={() => onOpenArtist(album.artist, album.key)}
                aria-label={`Abrir ${album.name} de ${album.artist}`}
              >
                {#if album.cover_url}
                  <img src={assetUrl(album.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
                {:else}
                  ♫
                {/if}
              </button>
              <strong>{album.name}</strong>
              <small>{album.artist}{album.year ? ` · ${album.year}` : ""}</small>
              <button
                class="album-card-play"
                onclick={() => onPlayCollection(album.tracks)}
                aria-label={`Reproducir ${album.name}`}
                title={`Reproducir ${album.name}`}
              >▶</button>
            </article>
          {/each}
        </div>
      </section>
    {/if}

    {#if results.tracks.length}
      <section class="search-section">
        <h3>Canciones</h3>
        <div class="song-list">
          {#each results.tracks as track, index (track.id)}
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
                <small>{text(track.artist, "Artista desconocido")}{track.album ? ` · ${track.album}` : ""}</small>
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
      </section>
    {/if}
  </div>
{/if}
