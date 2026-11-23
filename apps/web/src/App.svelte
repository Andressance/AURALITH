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
  let searchQuery = "";
  let visibleTracks = [];
  let selectedPlaylistId = null;
  let selectedPlaylist = null;
  const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

  async function api(path, options = {}) {
    if (!API_BASE) {
      throw new Error("VITE_API_URL is not configured in Vercel");
    }
    let response;
    try {
      response = await fetch(`${API_BASE}${path}`, { ...options, credentials: "include" });
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
      await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      await load();
    } catch (cause) {
      error = cause.message;
    }
  }

  async function load() {
    await api("/api/me");
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
    const file = event.target.files?.[0];
    if (!file) return;
    error = "";
    const form = new FormData();
    form.append("file", file);
    try {
      await api("/api/tracks", { method: "POST", body: form });
      await loadTracks();
    } catch (cause) {
      error = cause.message;
    }
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
    authenticated = false;
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
    currentTrack = track;
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
{:else}
  <main class="app-shell">
    <header>
      <h1>Auralith</h1>
      <div class="header-actions">
        <label class="upload">Upload MP3 / FLAC<input type="file" accept=".mp3,.flac,audio/mpeg,audio/flac" onchange={upload} /></label>
        <button class="secondary" onclick={downloadBackup}>Backup</button>
        <label class="upload">Restore<input type="file" accept=".zip" onchange={restoreBackup} /></label>
        <button class="secondary" onclick={logout}>Sign out</button>
      </div>
    </header>

    {#if error}<p class="error">{error}</p>{/if}

    <section>
      <h2>Library</h2>
      <input class="search" bind:value={searchQuery} oninput={search} placeholder="Search title, artist, album or genre" />
      <div class="track-list">
        {#each visibleTracks as track}
          <article>
            <button onclick={() => play(track)}>▶</button>
            <div>
              <strong>{track.title}</strong>
              <span>{track.artist || "Unknown artist"} · {track.album || "Unknown album"}</span>
            </div>
            <div class="track-actions">
              <button onclick={() => addToSelectedPlaylist(track)} aria-label="Add to selected playlist" title="Add to selected playlist">＋</button>
              <button onclick={() => favorite(track)} aria-label="Favorite" title="Favorite">♥</button>
              <button onclick={() => deleteTrack(track)} aria-label="Delete" title="Delete">×</button>
            </div>
          </article>
        {/each}
      </div>
    </section>

    <aside>
      <h2>Playlists</h2>
      <div class="playlist-create">
        <input bind:value={playlistName} placeholder="Playlist name" />
        <button onclick={createPlaylist}>Create</button>
      </div>
      {#each playlists as playlist}
        <button class="playlist-item" onclick={() => selectPlaylist(playlist)}>{playlist.name}</button>
      {/each}
      {#if selectedPlaylist}
        <h3>{selectedPlaylist.name}</h3>
        {#each selectedPlaylist.tracks as track}
          <div class="compact-track">
            <button onclick={() => play(track)}>▶</button>
            <span>{track.title}</span>
            <button onclick={() => removeFromPlaylist(track)}>×</button>
          </div>
        {/each}
      {/if}

      <h2>Favorites</h2>
      {#each favorites as track}
        <div class="compact-track">
          <button onclick={() => play(track)}>▶</button>
          <span>{track.title}</span>
          <button onclick={() => unfavorite(track)}>×</button>
        </div>
      {/each}
    </aside>
    {#if currentTrack}
      <footer class="player">
        <div>
          <strong>{currentTrack.title}</strong>
          <span>{currentTrack.artist || "Unknown artist"}</span>
        </div>
        <audio controls autoplay src={`/api/tracks/${currentTrack.id}/stream`}></audio>
      </footer>
    {/if}
  </main>
{/if}
