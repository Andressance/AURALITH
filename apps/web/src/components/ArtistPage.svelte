<script>
  import { assetUrl, hideBrokenImage, titleInitial } from "../lib/format.js";
  import { shuffleTracks } from "../lib/library.js";
  import SongList from "./SongList.svelte";

  export let artist;
  export let currentTrack;
  export let isPlaying;
  export let playCounts = {};
  export let initialAlbum = null;
  export let onBack;
  export let onPlayTrack;
  export let onPlayCollection;
  export let onEnqueue;

  let openAlbum = initialAlbum;
  let lastInitialAlbum = initialAlbum;
  let lastArtistKey = artist?.key;

  function formatDuration(seconds) {
    const total = Math.round(Number(seconds) || 0);
    if (total < 60) return `${total} s`;
    const hours = Math.floor(total / 3600);
    const minutes = Math.round((total % 3600) / 60);
    return hours ? `${hours} h ${minutes} min` : `${minutes} min`;
  }

  $: allSongs = [...(artist?.tracks || [])].sort(
    (a, b) =>
      String(a.album || "").localeCompare(String(b.album || ""), "es") ||
      String(a.title || "").localeCompare(String(b.title || ""), "es")
  );
  $: popular = [...(artist?.tracks || [])]
    .sort(
      (a, b) =>
        (playCounts[b.id] || 0) - (playCounts[a.id] || 0) ||
        String(a.title || "").localeCompare(String(b.title || ""), "es")
    )
    .slice(0, 5);
  $: openAlbumData = artist?.albums.find((album) => album.key === openAlbum) || null;
  $: totalDuration = formatDuration(artist?.duration || 0);

  // A new album request (from search or another artist) opens that album.
  $: if (initialAlbum !== lastInitialAlbum) {
    lastInitialAlbum = initialAlbum;
    if (initialAlbum) openAlbum = initialAlbum;
  }
  // Moving to another artist must not keep an album key from the previous one.
  $: if (artist?.key !== lastArtistKey) {
    lastArtistKey = artist?.key;
    openAlbum = initialAlbum;
  }
</script>

<section class="artist-page" aria-label={`Artista ${artist.name}`}>
  <button class="page-back" onclick={onBack}>← Volver</button>

  <header class="artist-hero">
    <div class="artist-hero-main">
      <div class="artist-portrait">
        {#if artist.cover_url}
          <img src={assetUrl(artist.cover_url)} alt="" onerror={hideBrokenImage} />
        {:else}
          {titleInitial(artist.name)}
        {/if}
      </div>
      <div class="artist-hero-copy">
        <span>Artista</span>
        <h2>{artist.name}</h2>
        <p>{artist.tracks.length} canciones · {artist.albums.length} álbumes · {totalDuration}</p>
        <div class="artist-actions">
          <button class="artist-play" onclick={() => onPlayCollection(allSongs)} disabled={!allSongs.length}>▶ Reproducir</button>
          <button class="artist-random" onclick={() => onPlayCollection(shuffleTracks(allSongs))} disabled={!allSongs.length}>⇄ Aleatorio</button>
        </div>
      </div>
    </div>
  </header>

  {#if popular.length}
    <section class="artist-section">
      <header>
        <h3>Populares</h3>
        <span>Según tus reproducciones en este dispositivo</span>
      </header>
      <SongList tracks={popular} {currentTrack} {isPlaying} {onPlayTrack} {onEnqueue} />
    </section>
  {/if}

  <section class="artist-section">
    <header>
      <h3>Álbumes</h3>
      <span>{artist.albums.length} en tu biblioteca</span>
    </header>
    <div class="album-grid">
      {#each artist.albums as album (album.key)}
        <article class="album-card" class:open={openAlbum === album.key}>
          <button
            class="album-card-cover"
            onclick={() => openAlbum = openAlbum === album.key ? null : album.key}
            aria-expanded={openAlbum === album.key}
            aria-label={`${openAlbum === album.key ? "Ocultar" : "Ver"} las canciones de ${album.name}`}
          >
            {#if album.cover_url}
              <img src={assetUrl(album.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
            {:else}
              ♫
            {/if}
          </button>
          <strong>{album.name}</strong>
          <small>{album.year ? `${album.year} · ` : ""}{album.tracks.length} {album.tracks.length === 1 ? "canción" : "canciones"}</small>
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

  {#if openAlbumData}
    <section class="artist-section artist-album">
      <header>
        <div>
          <h3>{openAlbumData.name}</h3>
          <span>{openAlbumData.year ? `${openAlbumData.year} · ` : ""}{openAlbumData.tracks.length} canciones</span>
        </div>
        <button class="artist-random" onclick={() => onPlayCollection(openAlbumData.tracks)}>▶ Reproducir álbum</button>
      </header>
      <SongList tracks={openAlbumData.tracks} {currentTrack} {isPlaying} {onPlayTrack} {onEnqueue} showAlbum={false} />
    </section>
  {/if}

  <section class="artist-section">
    <header>
      <h3>Canciones</h3>
      <span>{allSongs.length}</span>
    </header>
    <SongList tracks={allSongs} {currentTrack} {isPlaying} {onPlayTrack} {onEnqueue} />
  </section>
</section>
