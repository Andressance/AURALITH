<script>
  import { assetUrl } from "../lib/format.js";

  export let playlists;
  export let newPlaylistName;
  export let playerVisible;
  export let onClose;
  export let onCreateWithSelection;
  export let onAddToPlaylist;
</script>

<div class="playlist-picker" class:player-visible={playerVisible} role="dialog" aria-modal="true" aria-label="Añadir a playlist">
  <div class="sheet-heading">
    <strong>Añadir a una playlist</strong>
    <button onclick={onClose}>×</button>
  </div>
  <form onsubmit={onCreateWithSelection}>
    <input bind:value={newPlaylistName} placeholder="Nueva playlist" maxlength="200" />
    <button type="submit">Crear y añadir</button>
  </form>
  {#each playlists.filter((playlist) => !playlist.shared || playlist.role !== "viewer") as playlist}
    <button class="playlist-picker-item" onclick={() => onAddToPlaylist(playlist.id)}>
      {#if playlist.cover_url}
        <img src={assetUrl(playlist.cover_url)} alt="" loading="lazy" decoding="async" />
      {:else}
        <span>♫</span>
      {/if}
      <strong>{playlist.name}</strong>
    </button>
  {/each}
</div>
