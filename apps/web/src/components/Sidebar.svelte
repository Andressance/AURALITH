<script>
  import { assetUrl } from "../lib/format.js";

  export let activeView;
  export let showDevicesPanel;
  export let playlists;
  export let selectedPlaylistId;
  export let dragOverPlaylistId;
  export let playlistName;
  export let profile;
  export let profileName;
  export let onNavigate;
  export let onHome;
  export let onSearch;
  export let onToggleDevices;
  export let onUpload;
  export let onCreatePlaylist;
  export let onSelectPlaylist;
  export let onPlayPlaylist;
  export let onDragOver;
  export let onDragLeave;
  export let onDrop;
</script>

<aside class="sidebar">
  <a class="brand" href="/" aria-label="Auralith">
    <img src="/icon.svg" alt="" />
    <h1>Auralith</h1>
  </a>
  <nav>
    <button class="nav-item" class:active={activeView === "library"} onclick={onHome}>⌂ <span>Inicio</span></button>
    <button class="nav-item" onclick={onSearch}>⌕ <span>Buscar</span></button>
    <button class="nav-item" class:active={activeView === "playlists"} onclick={() => onNavigate("playlists")}>♫ <span>Playlists</span></button>
    <button class="nav-item" class:active={activeView === "profile"} onclick={() => onNavigate("profile")}>● <span>Perfil</span></button>
    <button class="nav-item" class:active={activeView === "jam"} onclick={() => onNavigate("jam")}>◉ <span>Jam</span></button>
    <button class="nav-item" class:active={showDevicesPanel} onclick={onToggleDevices}>◫ <span>Dispositivos</span></button>
  </nav>
  <div class="sidebar-library">
    <div class="sidebar-heading">
      <h2>Tu biblioteca</h2>
      <label class="icon-upload" title="Subir música">＋<input type="file" multiple accept=".mp3,.flac,audio/mpeg,audio/flac" onchange={onUpload} /></label>
    </div>
    <div class="playlist-create">
      <input bind:value={playlistName} placeholder="Nueva playlist" />
      <button onclick={onCreatePlaylist} aria-label="Crear playlist">＋</button>
    </div>
    {#each playlists.filter((playlist) => !playlist.shared || playlist.saved) as playlist}
      <div
        class="playlist-item"
        class:selected={selectedPlaylistId === playlist.id}
        class:drop-target={dragOverPlaylistId === playlist.id}
        role="group"
        aria-label={`Playlist ${playlist.name}`}
        ondragover={(event) => onDragOver(event, playlist.id)}
        ondragleave={onDragLeave}
        ondrop={(event) => onDrop(event, playlist.id)}
      >
        <button class="playlist-open" onclick={() => onSelectPlaylist(playlist)}>
          {#if playlist.cover_url}
            <img class="playlist-cover" src={assetUrl(playlist.cover_url)} alt="" loading="lazy" decoding="async" />
          {:else}
            <span class="playlist-cover">♫</span>
          {/if}
          <span><strong>{playlist.name}</strong><small>{playlist.shared ? `De ${playlist.owner}` : "Playlist"}</small></span>
        </button>
        <button
          class="playlist-play"
          onclick={(event) => { event.stopPropagation(); onPlayPlaylist(playlist); }}
          aria-label={`Reproducir playlist ${playlist.name}`}
          title={`Reproducir ${playlist.name}`}
        >
          ▶
        </button>
      </div>
    {/each}
  </div>
  <div class="sidebar-footer">
    <button class="profile-button" onclick={() => onNavigate("profile")}>
      {#if profile?.avatar_url}
        <img src={assetUrl(profile.avatar_url)} alt="" fetchpriority="high" decoding="async" />
      {:else}
        <span>{profileName.slice(0, 1).toUpperCase()}</span>
      {/if}
      <strong>{profileName}</strong>
    </button>
  </div>
</aside>
<button
  class="mobile-profile-button"
  aria-label={`Abrir perfil de ${profileName}`}
  onclick={() => onNavigate("profile")}
>
  {#if profile?.avatar_url}
    <img src={assetUrl(profile.avatar_url)} alt="" />
  {:else}
    <span>{profileName.slice(0, 1).toUpperCase()}</span>
  {/if}
</button>
