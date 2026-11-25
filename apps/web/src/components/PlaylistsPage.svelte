<script>
  import { assetUrl } from "../lib/format.js";

  export let playlists;
  export let playlistName;
  export let csvPlaylistName;
  export let csvImporting;
  export let csvImportReport;
  export let onCreatePlaylist;
  export let onImportCsv;
  export let onCloseReport;
  export let onConfirmCandidate;
  export let onNavigate;
  export let onSelectPlaylist;
  export let onToggleLibrary;
  export let onPlayPlaylist;
</script>

<section class="playlist-page">
  <div class="page-heading">
    <div>
      <span>Tu biblioteca</span>
      <h2>Playlists</h2>
    </div>
    <button class="primary-upload" onclick={() => playlistName = ""}>Nueva playlist</button>
  </div>
  <div class="playlist-create-page">
    <input bind:value={playlistName} placeholder="Nombre de la playlist" maxlength="200" />
    <button onclick={onCreatePlaylist}>Crear</button>
  </div>
  <form class="csv-import-form" onsubmit={onImportCsv}>
    <div>
      <strong>Importar desde CSV</strong>
      <span>Se añadirán automáticamente solo coincidencias exactas.</span>
    </div>
    <input bind:value={csvPlaylistName} maxlength="200" placeholder="Nombre de la playlist (opcional)" />
    <input type="file" accept=".csv,text/csv" required />
    <button type="submit" disabled={csvImporting}>
      {csvImporting ? "Importando…" : "Importar CSV"}
    </button>
  </form>
  {#if csvImportReport}
    <section class="csv-import-report" aria-live="polite">
      <div>
        <strong>{csvImportReport.playlist_name}</strong>
        <span>{csvImportReport.added} coincidencias exactas añadidas</span>
      </div>
      <button onclick={onCloseReport} aria-label="Cerrar informe">×</button>
      {#each csvImportReport.results as result}
        <article>
          <div>
            <strong>{result.title}</strong>
            <span>{result.artist || "Artista desconocido"} · {result.status.replaceAll("_", " ")}</span>
            {#if result.candidate}
              <small>Sugerencia: {result.candidate.title} — {result.candidate.artist || "Artista desconocido"}</small>
            {/if}
          </div>
          {#if result.candidate && !result.confirmed && result.status !== "EXACT"}
            <button onclick={() => onConfirmCandidate(result)}>Añadir</button>
          {:else if result.confirmed}
            <span class="csv-import-confirmed">Añadida</span>
          {/if}
        </article>
      {/each}
    </section>
  {/if}
  <div class="playlist-grid">
    {#each playlists as playlist}
      <article class="playlist-card">
        <button class="playlist-card-open" onclick={() => { onNavigate("library"); onSelectPlaylist(playlist); }}>
        {#if playlist.cover_url}
          <img src={assetUrl(playlist.cover_url)} alt="" />
        {:else}
          <span>♫</span>
        {/if}
        <strong>{playlist.name}</strong>
        <small>{playlist.shared ? `De ${playlist.owner}${playlist.role === "editor" ? " · colaboras" : ""}` : "Playlist"}</small>
        </button>
        {#if playlist.shared}
          <button class="playlist-library" class:saved={playlist.saved} onclick={() => onToggleLibrary(playlist)}>
            {playlist.saved ? "✓ En tu biblioteca" : "＋ Añadir a mi biblioteca"}
          </button>
        {/if}
        <button
          class="playlist-card-play"
          onclick={() => onPlayPlaylist(playlist)}
          aria-label={`Reproducir playlist ${playlist.name}`}
          title={`Reproducir ${playlist.name}`}
        >▶</button>
      </article>
    {/each}
  </div>
</section>
