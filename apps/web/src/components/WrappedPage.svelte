<script>
  import { assetUrl, hideBrokenImage, text } from "../lib/format.js";

  export let wrapped = null;
  export let years = [];
  export let year = new Date().getFullYear();
  export let loading = false;
  export let error = "";
  export let onChangeYear;
  export let onOpenArtist;

  const MONTHS = ["E", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

  function formatMinutes(seconds) {
    const minutes = Math.round((Number(seconds) || 0) / 60);
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    return `${hours} h ${minutes % 60} min`;
  }

  $: totalMinutes = Math.round((wrapped?.total_seconds || 0) / 60);
  $: hours = Math.floor(totalMinutes / 60);
  $: restMinutes = totalMinutes % 60;
  $: topArtistSeconds = wrapped?.top_artists?.[0]?.seconds || 0;
  $: maxMonth = Math.max(1, ...(wrapped?.monthly || []).map((item) => item.seconds));
  $: topTrack = wrapped?.top_tracks?.[0] || null;
</script>

<section class="wrapped-page">
  <header class="wrapped-heading">
    <span>Tu año en música</span>
    <h2>Wrapped {year}</h2>
  </header>

  {#if years.length > 1}
    <div class="wrapped-years" role="group" aria-label="Elegir año">
      {#each years as option}
        <button class:active={option === year} onclick={() => onChangeYear(option)}>{option}</button>
      {/each}
    </div>
  {/if}

  {#if loading}
    <p class="wrapped-status">Cargando tus estadísticas…</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if wrapped}
    {#if wrapped.total_plays === 0}
      <section class="wrapped-empty">
        <h3>Todavía no hay escuchas en {year}</h3>
        <p>
          Reproduce música y aquí aparecerán tus artistas, tus minutos y tu canción más
          escuchada de {year}. Las estadísticas empiezan a contarse desde ahora.
        </p>
      </section>
    {:else}
      <section class="wrapped-hero">
        <div class="wrapped-hero-copy">
          <span>Has escuchado</span>
          <strong>{hours > 0 ? `${hours} h ${restMinutes} min` : `${totalMinutes} min`}</strong>
          <p>{wrapped.total_plays} reproducciones · {wrapped.unique_artists} artistas · {wrapped.unique_tracks} canciones</p>
        </div>
        <div class="wrapped-hero-year" aria-hidden="true">{year}</div>
      </section>

      {#if topTrack}
        <section class="wrapped-section">
          <h3>Tu canción del año</h3>
          <article class="wrapped-top-track">
            <div class="wrapped-top-cover">
              {#if topTrack.cover_url}
                <img src={assetUrl(topTrack.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
              {:else}
                ♫
              {/if}
            </div>
            <div class="wrapped-top-copy">
              <strong>{text(topTrack.title, "Canción sin título")}</strong>
              <button class="track-artist" onclick={() => onOpenArtist(topTrack.artist)}>{text(topTrack.artist, "Artista desconocido")}</button>
              <span>{topTrack.plays} reproducciones · {formatMinutes(topTrack.seconds)}</span>
            </div>
          </article>
        </section>
      {/if}

      {#if wrapped.top_artists.length}
        <section class="wrapped-section">
          <h3>Tus artistas</h3>
          <div class="wrapped-artists">
            {#each wrapped.top_artists as artist, index}
              <article class="wrapped-artist">
                <span class="wrapped-rank">{index + 1}</span>
                <span class="wrapped-artist-art">
                  {#if artist.cover_url}
                    <img src={assetUrl(artist.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
                  {:else}
                    {text(artist.name, "?").slice(0, 1).toUpperCase()}
                  {/if}
                </span>
                <div class="wrapped-artist-copy">
                  <button class="wrapped-artist-name" onclick={() => onOpenArtist(artist.name)}>{artist.name}</button>
                  <div class="wrapped-bar">
                    <span style={`width: ${topArtistSeconds ? Math.max(4, Math.round((artist.seconds / topArtistSeconds) * 100)) : 0}%`}></span>
                  </div>
                  <small>{formatMinutes(artist.seconds)} · {artist.plays} reproducciones</small>
                </div>
              </article>
            {/each}
          </div>
        </section>
      {/if}

      {#if wrapped.top_tracks.length > 1}
        <section class="wrapped-section">
          <h3>Tus canciones</h3>
          <div class="wrapped-track-list">
            {#each wrapped.top_tracks.slice(1, 6) as track, index}
              <article>
                <span class="wrapped-rank">{index + 2}</span>
                <button class="wrapped-track-title" onclick={() => onOpenArtist(track.artist)}>
                  <strong>{text(track.title, "Canción sin título")}</strong>
                  <small>{text(track.artist, "Artista desconocido")}</small>
                </button>
                <span class="wrapped-track-plays">{track.plays} ×</span>
                <span class="wrapped-track-time">{formatMinutes(track.seconds)}</span>
              </article>
            {/each}
          </div>
        </section>
      {/if}

      {#if wrapped.top_albums.length}
        <section class="wrapped-section">
          <h3>Tus álbumes</h3>
          <div class="wrapped-albums">
            {#each wrapped.top_albums.slice(0, 6) as album}
              <article class="wrapped-album">
                <span class="wrapped-album-cover">
                  {#if album.cover_url}
                    <img src={assetUrl(album.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
                  {:else}
                    ♫
                  {/if}
                </span>
                <strong>{album.name}</strong>
                <button class="track-artist" onclick={() => onOpenArtist(album.artist)}>{album.artist}</button>
                <small>{formatMinutes(album.seconds)}</small>
              </article>
            {/each}
          </div>
        </section>
      {/if}

      <section class="wrapped-section">
        <h3>Cómo escuchaste {year}</h3>
        <div class="wrapped-months" role="img" aria-label={`Minutos por mes de ${year}`}>
          {#each wrapped.monthly as month, index}
            <span class="wrapped-month" title={`${MONTHS[index]}: ${formatMinutes(month.seconds)}`}>
              <span class="wrapped-month-bar" style={`height: ${Math.max(3, Math.round((month.seconds / maxMonth) * 100))}%`}></span>
              <small>{MONTHS[index]}</small>
            </span>
          {/each}
        </div>
        {#if wrapped.busiest_day}
          <p class="wrapped-hint">
            Tu día más musical fue el {wrapped.busiest_day.date} con {formatMinutes(wrapped.busiest_day.seconds)}.
          </p>
        {/if}
      </section>
    {/if}
  {:else}
    <p class="wrapped-status">Sin datos todavía.</p>
  {/if}
</section>
