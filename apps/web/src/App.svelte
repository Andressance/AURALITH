<script>
  let authenticated = false;
  let username = "owner";
  let password = "";
  let tracks = [];
  let playlists = [];
  let favorites = [];
  let playlistName = "";
  let error = "";
  let audio;
  let currentTrack;
  let uploadProgress = "";
  let uploading = false;
  let uploadQueue = [];
  let isPlaying = false;
  let progress = 0;
  let duration = 0;
  let volume = 0.8;
  let searchQuery = "";
  let visibleTracks = [];
  let selectedPlaylistId = null;
  let selectedPlaylist = null;
  let sessionToken = localStorage.getItem("auralith_session_token") || "";
  let profile = null;
  let profileName = "";
  let profileUsername = "";
  let selectedTrackIds = [];
  let showPlaylistPicker = false;
  let newPlaylistName = "";
  let activeView = "library";
  let playerVisible = false;
  let pullDistance = 0;
  let pullStart = 0;
  let pulling = false;
  let refreshing = false;
  const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

  function text(value, fallback = "") {
    return typeof value === "string" ? value : fallback;
  }

  function streamUrl(track) {
    const token = sessionToken ? `?token=${encodeURIComponent(sessionToken)}` : "";
    return `${API_BASE}/api/tracks/${track.id}/stream${token}`;
  }

  function assetUrl(path) {
    if (!path) return "";
    const token = sessionToken ? `?token=${encodeURIComponent(sessionToken)}` : "";
    return `${API_BASE}${path}${token}`;
  }

  function titleInitial(title) {
    const value = text(title).trim();
    return value ? value.slice(0, 1).toUpperCase() : "♫";
  }

  async function api(path, options = {}) {
    if (!API_BASE) {
      throw new Error("VITE_API_URL is not configured in Vercel");
    }
    let response;
    try {
      const headers = new Headers(options.headers || {});
      if (sessionToken) headers.set("Authorization", `Bearer ${sessionToken}`);
      response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
        credentials: "include"
      });
      if (response.status === 401) {
        sessionToken = "";
        localStorage.removeItem("auralith_session_token");
        authenticated = false;
      }
    } catch {
      throw new Error(`Unable to reach API: ${API_BASE}`);
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "Request failed");
    }
    return response.status === 204 ? null : response.json();
  }

  async function login(event) {
    event.preventDefault();
    error = "";
    try {
      const result = await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      if (result.token) {
        sessionToken = result.token;
        localStorage.setItem("auralith_session_token", result.token);
      }
      await load();
    } catch (cause) {
      error = cause.message;
    }
  }

  async function load() {
    profile = await api("/api/me");
    profileName = profile.display_name || profile.username;
    profileUsername = profile.username;
    authenticated = true;
    await Promise.all([loadTracks(), loadPlaylists(), loadFavorites()]);
  }

  async function loadTracks() {
    tracks = await api("/api/tracks");
    visibleTracks = tracks;
  }

  async function search() {
    if (!searchQuery.trim()) {
      visibleTracks = tracks;
      return;
    }
    visibleTracks = await api(`/api/search?q=${encodeURIComponent(searchQuery)}`);
  }

  async function loadPlaylists() {
    playlists = await api("/api/playlists");
  }

  async function loadFavorites() {
    favorites = await api("/api/favorites");
  }

  async function upload(event) {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    error = "";
    uploading = true;
    uploadQueue = files.map((file) => ({
      name: file.name,
      status: "pending",
      detail: "En cola"
    }));
    uploadProgress = `0 de ${files.length} completadas`;

    for (let index = 0; index < files.length; index += 1) {
      const file = files[index];
      uploadQueue = uploadQueue.map((item, itemIndex) =>
        itemIndex === index
          ? { ...item, status: "uploading", detail: "Subiendo..." }
          : item
      );
      uploadProgress = `${index} de ${files.length} completadas`;
      const form = new FormData();
      form.append("file", file);
      try {
        const uploadedTrack = await api("/api/tracks", { method: "POST", body: form });
        if (selectedPlaylistId && uploadedTrack.id) {
          await api(`/api/playlists/${selectedPlaylistId}/tracks/${uploadedTrack.id}`, { method: "POST" });
        }
        uploadQueue = uploadQueue.map((item, itemIndex) =>
          itemIndex === index
            ? { ...item, status: "done", detail: uploadedTrack.duplicate ? "Ya estaba en la biblioteca" : "Subida completada" }
            : item
        );
      } catch (cause) {
        uploadQueue = uploadQueue.map((item, itemIndex) =>
          itemIndex === index
            ? { ...item, status: "error", detail: cause.message }
            : item
        );
        error = "Algunas canciones no se pudieron subir.";
      }
    }
    uploadProgress = `${files.length} de ${files.length} completadas`;
    uploading = false;
    event.target.value = "";
    await Promise.all([
      loadTracks(),
      selectedPlaylistId ? selectPlaylist(playlists.find((playlist) => playlist.id === selectedPlaylistId) || { id: selectedPlaylistId }) : Promise.resolve()
    ]);
  }

  async function createPlaylist() {
    if (!playlistName.trim()) return;
    await api("/api/playlists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: playlistName })
    });
    playlistName = "";
    await loadPlaylists();
  }

  async function favorite(track) {
    await api(`/api/favorites/${track.id}`, { method: "POST" });
    await loadFavorites();
  }

  async function unfavorite(track) {
    await api(`/api/favorites/${track.id}`, { method: "DELETE" });
    await loadFavorites();
  }

  async function selectPlaylist(playlist) {
    selectedPlaylistId = playlist.id;
    selectedPlaylist = await api(`/api/playlists/${playlist.id}`);
  }

  async function addToSelectedPlaylist(track) {
    if (!selectedPlaylistId) return;
    await api(`/api/playlists/${selectedPlaylistId}/tracks/${track.id}`, { method: "POST" });
    selectedPlaylist = await api(`/api/playlists/${selectedPlaylistId}`);
  }

  function toggleTrackSelection(trackId) {
    selectedTrackIds = selectedTrackIds.includes(trackId)
      ? selectedTrackIds.filter((id) => id !== trackId)
      : [...selectedTrackIds, trackId];
  }

  async function addSelectedToPlaylist(playlistId) {
    if (!selectedTrackIds.length) return;
    await api(`/api/playlists/${playlistId}/tracks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ track_ids: selectedTrackIds })
    });
    selectedTrackIds = [];
    showPlaylistPicker = false;
    await loadPlaylists();
  }

  async function createPlaylistWithSelection(event) {
    event.preventDefault();
    if (!newPlaylistName.trim()) return;
    await api("/api/playlists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: newPlaylistName.trim(),
        track_ids: selectedTrackIds
      })
    });
    newPlaylistName = "";
    selectedTrackIds = [];
    showPlaylistPicker = false;
    await loadPlaylists();
  }

  async function removeFromPlaylist(track) {
    await api(`/api/playlists/${selectedPlaylistId}/tracks/${track.id}`, { method: "DELETE" });
    selectedPlaylist = await api(`/api/playlists/${selectedPlaylistId}`);
  }

  async function deleteTrack(track) {
    await api(`/api/tracks/${track.id}`, { method: "DELETE" });
    if (selectedPlaylistId) selectedPlaylist = await api(`/api/playlists/${selectedPlaylistId}`);
    await Promise.all([loadTracks(), loadFavorites()]);
  }

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    sessionToken = "";
    localStorage.removeItem("auralith_session_token");
    authenticated = false;
  }

  async function saveProfile(event) {
    event.preventDefault();
    try {
      profile = await api("/api/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: profileUsername, display_name: profileName })
      });
      profileName = profile.display_name;
      activeView = "library";
    } catch (cause) {
      error = cause.message;
    }
  }

  async function uploadProfileAvatar(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      await api("/api/profile/avatar", { method: "POST", body: form });
      profile = await api("/api/me");
    } catch (cause) {
      error = cause.message;
    }
  }

  async function uploadPlaylistCover(event) {
    const file = event.target.files?.[0];
    if (!file || !selectedPlaylistId) return;
    const form = new FormData();
    form.append("file", file);
    try {
      await api(`/api/playlists/${selectedPlaylistId}/cover`, { method: "POST", body: form });
      selectedPlaylist = await api(`/api/playlists/${selectedPlaylistId}`);
      await loadPlaylists();
    } catch (cause) {
      error = cause.message;
    }
  }

  function downloadBackup() {
    window.open("/api/backup", "_blank");
  }

  async function restoreBackup(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    try {
      await api("/api/restore", { method: "POST", body: form });
      await load();
      error = "";
    } catch (cause) {
      error = cause.message;
    }
  }

  function play(track) {
    if (currentTrack?.id === track.id && audio) {
      if (audio.paused) {
        audio.play();
        playerVisible = true;
      } else {
        audio.pause();
      }
      return;
    }
    currentTrack = track;
    playerVisible = true;
    progress = 0;
    duration = 0;
    updateMediaSession(track);
  }

  function togglePlayback() {
    if (!audio) return;
    if (audio.paused) {
      audio.play();
      playerVisible = true;
    } else {
      audio.pause();
    }
  }

  function seek(event) {
    if (!audio || !duration) return;
    const next = Number(event.currentTarget.value);
    audio.currentTime = next;
    progress = next;
  }

  function changeVolume(event) {
    volume = Number(event.currentTarget.value);
    if (audio) audio.volume = volume;
  }

  function formatTime(seconds) {
    if (!Number.isFinite(seconds)) return "0:00";
    const minutes = Math.floor(seconds / 60);
    return `${minutes}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
  }

  function pullTouchStart(event) {
    if (event.touches.length !== 1) return;
    const panel = event.currentTarget;
    if (panel.scrollTop <= 0) {
      pullStart = event.touches[0].clientY;
      pulling = true;
    }
  }

  function pullTouchMove(event) {
    if (!pulling) return;
    const distance = event.touches[0].clientY - pullStart;
    if (distance > 0) {
      pullDistance = Math.min(distance * 0.55, 96);
    }
  }

  async function pullTouchEnd() {
    if (!pulling) return;
    pulling = false;
    if (pullDistance >= 64) {
      refreshing = true;
      pullDistance = 64;
      await Promise.all([loadTracks(), loadPlaylists(), loadFavorites()]);
    }
    refreshing = false;
    pullDistance = 0;
  }

  function updateMediaSession(track) {
    if (!("mediaSession" in navigator) || !track) return;
    const artwork = track.cover_url
      ? [{ src: assetUrl(track.cover_url), sizes: "512x512", type: "image/jpeg" }]
      : [{ src: `${window.location.origin}/icon.svg`, sizes: "any", type: "image/svg+xml" }];
    navigator.mediaSession.metadata = new MediaMetadata({
      title: text(track.title, "Canción sin título"),
      artist: text(track.artist, "Auralith"),
      album: text(track.album, "Auralith"),
      artwork
    });
    navigator.mediaSession.setActionHandler("play", () => {
      audio?.play();
    });
    navigator.mediaSession.setActionHandler("pause", () => {
      audio?.pause();
    });
    navigator.mediaSession.setActionHandler("seekto", (details) => {
      if (audio && Number.isFinite(details.seekTime)) audio.currentTime = details.seekTime;
    });
  }

  load().catch(() => {});
</script>

{#if !authenticated}
  <main class="login-shell">
    <form onsubmit={(event) => login(event)}>
      <h1>Auralith</h1>
      <p>Your private music cloud.</p>
      <label>
        Username
        <input bind:value={username} autocomplete="username" />
      </label>
      <label>
        Password
        <input type="password" bind:value={password} autocomplete="current-password" />
      </label>
      {#if error}<p class="error">{error}</p>{/if}
      <button type="submit">Sign in</button>
    </form>
  </main>

  {#if selectedTrackIds.length}
    <section class="selection-bar">
      <strong>{selectedTrackIds.length} seleccionada(s)</strong>
      <button onclick={() => showPlaylistPicker = true}>Añadir a playlist</button>
      <button class="selection-clear" onclick={() => selectedTrackIds = []}>Cancelar</button>
    </section>
  {/if}

  {#if showPlaylistPicker}
    <div class="playlist-picker" role="dialog" aria-modal="true" aria-label="Añadir a playlist">
      <div class="sheet-heading">
        <strong>Añadir a una playlist</strong>
        <button onclick={() => showPlaylistPicker = false}>×</button>
      </div>
      <form onsubmit={createPlaylistWithSelection}>
        <input bind:value={newPlaylistName} placeholder="Nueva playlist" maxlength="200" />
        <button type="submit">Crear y añadir</button>
      </form>
      {#each playlists as playlist}
        <button class="playlist-picker-item" onclick={() => addSelectedToPlaylist(playlist.id)}>
          {#if playlist.cover_url}
            <img src={assetUrl(playlist.cover_url)} alt="" />
          {:else if activeView === "library"}
            <span>♫</span>
          {/if}
          <strong>{playlist.name}</strong>
        </button>
      {/each}
    </div>
  {/if}
{:else}
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="/" aria-label="Auralith">
        <img src="/icon.svg" alt="" />
        <h1>Auralith</h1>
      </a>
      <nav>
        <button class="nav-item" class:active={activeView === "library"} onclick={() => { activeView = "library"; visibleTracks = tracks; selectedPlaylistId = null; selectedPlaylist = null; }}>⌂ <span>Inicio</span></button>
        <button class="nav-item" onclick={() => { activeView = "library"; searchQuery = ""; search(); }}>⌕ <span>Buscar</span></button>
        <button class="nav-item" class:active={activeView === "playlists"} onclick={() => activeView = "playlists"}>♫ <span>Playlists</span></button>
        <button class="nav-item" class:active={activeView === "profile"} onclick={() => activeView = "profile"}>● <span>Perfil</span></button>
      </nav>
      <div class="sidebar-library">
        <div class="sidebar-heading">
          <h2>Tu biblioteca</h2>
          <label class="icon-upload" title="Subir música">＋<input type="file" multiple accept=".mp3,.flac,audio/mpeg,audio/flac" onchange={upload} /></label>
        </div>
        <div class="playlist-create">
          <input bind:value={playlistName} placeholder="Nueva playlist" />
          <button onclick={createPlaylist} aria-label="Crear playlist">＋</button>
        </div>
        {#each playlists as playlist}
          <button class="playlist-item" class:selected={selectedPlaylistId === playlist.id} onclick={() => selectPlaylist(playlist)}>
            <span class="playlist-cover">♫</span>
            <span><strong>{playlist.name}</strong><small>Playlist</small></span>
          </button>
        {/each}
      </div>
      <div class="sidebar-footer">
        <button class="profile-button" onclick={() => activeView = "profile"}>
          {#if profile?.avatar_url}
            <img src={assetUrl(profile.avatar_url)} alt="" />
          {:else}
            <span>{profileName.slice(0, 1).toUpperCase()}</span>
          {/if}
          <strong>{profileName}</strong>
        </button>
        <button onclick={downloadBackup}>Copia de seguridad</button>
        <label>Restaurar<input type="file" accept=".zip" onchange={restoreBackup} /></label>
        <button onclick={logout}>Cerrar sesión</button>
      </div>
    </aside>
    <button
      class="mobile-profile-button"
      aria-label={`Abrir perfil de ${profileName}`}
      onclick={() => activeView = "profile"}
    >
      {#if profile?.avatar_url}
        <img src={assetUrl(profile.avatar_url)} alt="" />
      {:else}
        <span>{profileName.slice(0, 1).toUpperCase()}</span>
      {/if}
    </button>

    <main
      class="main-panel"
      ontouchstart={pullTouchStart}
      ontouchmove={pullTouchMove}
      ontouchend={pullTouchEnd}
    >
      {#if pullDistance > 0}
        <div
          class="pull-refresh"
          class:ready={pullDistance >= 64}
          style={`transform: translateY(${pullDistance}px)`}
        >
          <span>{refreshing ? "↻" : pullDistance >= 64 ? "↓" : "↕"}</span>
        </div>
      {/if}
      {#if error}<p class="error">{error}</p>{/if}
      {#if activeView === "profile"}
        <section class="profile-page">
          <button class="page-back" onclick={() => activeView = "library"}><span>←</span> Volver a la biblioteca</button>
          <div class="profile-hero">
            <div class="profile-avatar-large">
              {#if profile?.avatar_url}
                <img src={assetUrl(profile.avatar_url)} alt="" />
              {:else}
                <span>{profileName.slice(0, 1).toUpperCase()}</span>
              {/if}
              <label title="Cambiar foto">✎<input type="file" accept="image/jpeg,image/png,image/webp" onchange={uploadProfileAvatar} /></label>
            </div>
            <div class="profile-heading">
              <span>Perfil</span>
              <h2>{profileName}</h2>
              <p>@{profileUsername} · {profile?.role === "owner" ? "Propietario" : "Invitado"}</p>
            </div>
          </div>
          <form class="profile-form" onsubmit={saveProfile}>
            <section class="profile-form-section">
              <div>
                <span>Detalles públicos</span>
                <p>Cómo quieres que aparezca tu nombre dentro de Auralith.</p>
              </div>
              <label>
                <span>Nombre visible</span>
                <input bind:value={profileName} maxlength="100" placeholder="Tu nombre" />
              </label>
            </section>
            <section class="profile-form-section">
              <div>
                <span>Cuenta</span>
                <p>Usuario que utilizas para iniciar sesión.</p>
              </div>
              <label>
                <span>Usuario</span>
                <input bind:value={profileUsername} maxlength="63" autocomplete="username" />
              </label>
            </section>
            <div class="profile-actions">
              <button type="button" class="profile-cancel" onclick={() => activeView = "library"}>Cancelar</button>
              <button type="submit" class="profile-save">Guardar cambios</button>
            </div>
          </form>
        </section>
      {:else if activeView === "playlists"}
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
            <button onclick={createPlaylist}>Crear</button>
          </div>
          <div class="playlist-grid">
            {#each playlists as playlist}
              <button class="playlist-card" onclick={() => { selectPlaylist(playlist); activeView = "library"; }}>
                {#if playlist.cover_url}
                  <img src={assetUrl(playlist.cover_url)} alt="" />
                {:else}
                  <span>♫</span>
                {/if}
                <strong>{playlist.name}</strong>
                <small>Playlist</small>
              </button>
            {/each}
          </div>
        </section>
      {/if}
      {#if uploadQueue.length}
        <section class="upload-panel" aria-live="polite">
          <div class="upload-summary">
            <div>
              <strong>{uploading ? "Subiendo canciones" : "Subida finalizada"}</strong>
              <span>{uploadProgress}</span>
            </div>
            {#if !uploading}
              <button onclick={() => uploadQueue = []} aria-label="Cerrar resumen">×</button>
            {/if}
          </div>
          <div class="upload-progress-bar">
            <span style={`width: ${(uploadQueue.filter((item) => item.status === "done" || item.status === "error").length / uploadQueue.length) * 100}%`}></span>
          </div>
          <div class="upload-list">
            {#each uploadQueue as item}
              <div class={`upload-item ${item.status}`}>
                <span class="upload-status">
                  {item.status === "done" ? "✓" : item.status === "error" ? "!" : item.status === "uploading" ? "↻" : "·"}
                </span>
                <div>
                  <strong>{item.name}</strong>
                  <small>{item.detail}</small>
                </div>
              </div>
            {/each}
          </div>
        </section>
      {/if}
      {#if activeView === "library"}
        <header class="topbar">
          <input class="search" bind:value={searchQuery} oninput={search} placeholder="¿Qué quieres reproducir?" />
        </header>
      {/if}

      {#if activeView === "library" && selectedPlaylist}
        <section class="playlist-hero">
          <div class="hero-cover">
            {#if selectedPlaylist.cover_url}
              <img src={assetUrl(selectedPlaylist.cover_url)} alt="" />
            {:else}
              ♫
            {/if}
            <label title="Cambiar foto">✎<input type="file" accept="image/jpeg,image/png,image/webp" onchange={uploadPlaylistCover} /></label>
          </div>
          <div>
            <span>Playlist</span>
            <h2>{selectedPlaylist.name}</h2>
            <p>Auralith · {selectedPlaylist.tracks.length} canciones</p>
          </div>
        </section>
        <section class="track-list playlist-tracks">
          {#each selectedPlaylist.tracks as track, index}
            <article class:playing={currentTrack?.id === track.id}>
              <span class="track-index">{index + 1}</span>
              <button class="track-play" onclick={() => play(track)}>{currentTrack?.id === track.id && isPlaying ? "Ⅱ" : "▶"}</button>
              <div><strong>{text(track.title, "Canción sin título")}</strong><span>{text(track.artist, "Artista desconocido")}</span></div>
              <button class="row-action" onclick={() => removeFromPlaylist(track)} title="Quitar">×</button>
            </article>
          {/each}
        </section>
      {:else}
        <section class="library-header">
          <div><span>Tu música</span><h2>Made for you</h2></div>
          <label class="primary-upload" class:disabled={uploading}>Subir canciones<input type="file" multiple accept=".mp3,.flac,audio/mpeg,audio/flac" onchange={upload} disabled={uploading} /></label>
        </section>
        <section class="track-grid">
          {#each visibleTracks as track}
            <article class:playing={currentTrack?.id === track.id}>
              <label class="track-select">
                <input
                  type="checkbox"
                  checked={selectedTrackIds.includes(track.id)}
                  onchange={() => toggleTrackSelection(track.id)}
                  aria-label={`Seleccionar ${text(track.title, "Canción")}`}
                />
              </label>
              <button class="cover" onclick={() => play(track)} aria-label={`Reproducir ${text(track.title, "Canción sin título")}`}>
                {#if track.cover_url}
                  <img src={assetUrl(track.cover_url)} alt="" />
                {:else}
                  <span>{titleInitial(track.title)}</span>
                {/if}
                <b>{currentTrack?.id === track.id && isPlaying ? "Ⅱ" : "▶"}</b>
              </button>
              <strong>{text(track.title, "Canción sin título")}</strong>
              <span>{text(track.artist, "Artista desconocido")}</span>
              <div class="track-actions">
                <button onclick={() => favorite(track)} aria-label="Favorito" title="Favorito">♥</button>
                <button onclick={() => deleteTrack(track)} aria-label="Eliminar" title="Eliminar">×</button>
              </div>
            </article>
          {/each}
        </section>
      {/if}
    </main>

    {#if currentTrack && playerVisible}
      <footer class="player">
        <div class="now-playing">
          <div class="mini-cover">
            {#if currentTrack.cover_url}
              <img src={assetUrl(currentTrack.cover_url)} alt="" />
            {:else}
              ♫
            {/if}
          </div>
          <div><strong>{text(currentTrack.title, "Canción sin título")}</strong><span>{text(currentTrack.artist, "Artista desconocido")}</span></div>
        </div>
        <div class="player-center">
          <button class="player-toggle" onclick={togglePlayback}>{isPlaying ? "Ⅱ" : "▶"}</button>
          <div class="timeline">
            <span>{formatTime(progress)}</span>
            <input aria-label="Posición" type="range" min="0" max={duration || 0} value={progress} oninput={seek} />
            <span>{formatTime(duration)}</span>
          </div>
        </div>
        <input class="volume" aria-label="Volumen" type="range" min="0" max="1" step="0.05" value={volume} oninput={changeVolume} />
        <audio
          bind:this={audio}
          autoplay
          preload="metadata"
          src={streamUrl(currentTrack)}
          onplay={() => isPlaying = true}
          onpause={() => isPlaying = false}
          ontimeupdate={(event) => progress = event.currentTarget.currentTime}
          onloadedmetadata={(event) => duration = event.currentTarget.duration}
          onvolumechange={(event) => volume = event.currentTarget.volume}
        ></audio>
      </footer>
    {/if}
  </div>
{/if}
