<script>
  import { assetUrl, text } from "../lib/format.js";

  export let jamCode;
  export let jamState;
  export let jamError;
  export let jamJoinCode;
  export let jamSearch;
  export let tracks;
  export let profile;
  export let onCreate;
  export let onJoin;
  export let onLeave;
  export let onEnd;
  // Inside a jam, the app's play/pause sends the jam control with the current position.
  export let onTogglePlayback;
  export let onControl;
  export let onMoveQueueItem;
  export let onRemoveQueueItem;
  export let onPlayTrack;
  export let onEnqueue;

  function jamLibrary(query, library) {
    const needle = query.trim().toLowerCase();
    if (!needle) return library;
    return library.filter((track) =>
      [track.title, track.artist, track.album].some((value) => String(value || "").toLowerCase().includes(needle))
    );
  }
</script>

<section class="jam-page">
  <header class="jam-header">
    <div><span>Escuchar juntos</span><h2>Jam</h2></div>
    {#if jamCode}
      <button class="jam-leave" onclick={onLeave}>Salir</button>
    {/if}
  </header>

  {#if jamError}<p class="error">{jamError}</p>{/if}

  {#if !jamCode}
    <div class="jam-start">
      <article class="jam-card">
        <strong>Crea un jam</strong>
        <p>Comparte el código y escuchad lo mismo a la vez. Cualquiera puede cambiar de canción.</p>
        <button class="primary-upload" onclick={onCreate}>Crear jam</button>
      </article>
      <article class="jam-card">
        <strong>Entrar en un jam</strong>
        <p>Pide el código a quien lo haya creado.</p>
        <form onsubmit={(event) => { event.preventDefault(); onJoin(); }}>
          <input bind:value={jamJoinCode} placeholder="Código" maxlength="12" />
          <button type="submit">Entrar</button>
        </form>
      </article>
    </div>
  {:else}
    <div class="jam-code">
      <span>Código del jam</span>
      <strong>{jamCode}</strong>
      <button onclick={() => navigator.clipboard?.writeText(jamCode)}>Copiar</button>
    </div>

    <div class="jam-now">
      <div class="jam-cover">
        {#if jamState?.current_track?.cover_url}
          <img src={assetUrl(jamState.current_track.cover_url)} alt="" />
        {:else}
          ♫
        {/if}
      </div>
      <div class="jam-now-text">
        <span>{jamState?.is_playing ? "Sonando ahora" : jamState?.current_track ? "En pausa" : "Nada sonando"}</span>
        <strong>{jamState?.current_track ? text(jamState.current_track.title, "Canción sin título") : "Elige una canción"}</strong>
        <small>{jamState?.current_track ? text(jamState.current_track.artist, "Artista desconocido") : "Pulsa ▶ en la biblioteca de abajo para empezar a sonar todos a la vez"}</small>
      </div>
      <div class="jam-controls">
        <button onclick={() => onTogglePlayback()} disabled={!jamState?.current_track}>
          {jamState?.is_playing ? "Ⅱ Pausar" : "▶ Reproducir"}
        </button>
        <button onclick={() => onControl("next")} disabled={!jamState?.queue?.length}>⏭ Siguiente</button>
      </div>
    </div>

    <div class="jam-people">
      {#each jamState?.participants || [] as person}
        <span class="jam-person">{person.display_name || person.username}{person.id === jamState.host_user_id ? " · anfitrión" : ""}</span>
      {/each}
    </div>

    <div class="jam-columns">
      <section class="jam-panel">
        <h3>A continuación <small>{jamState?.queue?.length || 0}</small></h3>
        <p class="jam-hint">La primera de la lista es la siguiente. Ordénalas con ↑ ↓.</p>
        {#each jamState?.queue || [] as item, index (item.id)}
          <div class="jam-row">
            <span>{text(item.track.title, "Canción sin título")}<small>{text(item.track.artist, "Artista desconocido")}</small></span>
            <div class="jam-row-actions">
              <button onclick={() => onMoveQueueItem(item, "up")} disabled={index === 0} aria-label="Subir">↑</button>
              <button onclick={() => onMoveQueueItem(item, "down")} disabled={index === jamState.queue.length - 1} aria-label="Bajar">↓</button>
              <button onclick={() => onRemoveQueueItem(item)} aria-label="Quitar de la cola">Quitar</button>
            </div>
          </div>
        {:else}
          <p class="jam-empty">Nada en cola. Cuando termine la canción, el jam pasará a la siguiente de aquí.</p>
        {/each}
      </section>
      <section class="jam-panel">
        <h3>Biblioteca</h3>
        <input class="jam-search" type="search" bind:value={jamSearch} placeholder="Buscar canción o artista" aria-label="Buscar en tu biblioteca" />
        {#each jamLibrary(jamSearch, tracks) as track (track.id)}
          <div class="jam-row">
            <span>{text(track.title, "Canción sin título")}<small>{text(track.artist, "Artista desconocido")}</small></span>
            <div class="jam-row-actions">
              <button onclick={() => onPlayTrack(track)} aria-label={`Reproducir ${text(track.title, "canción")} ahora`}>▶ Ahora</button>
              <button onclick={() => onEnqueue(track, true)} aria-label={`Poner ${text(track.title, "canción")} la siguiente`}>⏭ Siguiente</button>
              <button onclick={() => onEnqueue(track)} aria-label={`Añadir ${text(track.title, "canción")} al final`}>+ Cola</button>
            </div>
          </div>
        {:else}
          <p class="jam-empty">{tracks.length ? "Ninguna canción coincide con la búsqueda." : "Sube música para añadirla."}</p>
        {/each}
      </section>
    </div>

    {#if profile && jamState?.host_user_id === profile.id}
      <button class="jam-end" onclick={onEnd}>Terminar el jam</button>
    {/if}
  {/if}
</section>
