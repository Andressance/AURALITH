<script>
  export let fileCount;
  export let playlists;
  export let uploadNewPlaylistName;
  export let uploadPlaylistIds;
  export let onClose;
  export let onToggle;
  export let onConfirm;
</script>

<div class="upload-playlist-picker" role="dialog" aria-modal="true" aria-label="Añadir canciones al subir">
  <div class="sheet-heading">
    <strong>Añadir las {fileCount} canciones a playlists</strong>
    <button onclick={onClose}>×</button>
  </div>
  <form onsubmit={(event) => { event.preventDefault(); onConfirm(); }}>
    <input bind:value={uploadNewPlaylistName} placeholder="Crear una nueva playlist" maxlength="200" />
    <div class="upload-playlist-options">
      {#each playlists.filter((playlist) => !playlist.shared || playlist.role !== "viewer") as playlist}
        <label>
          <input
            type="checkbox"
            checked={uploadPlaylistIds.includes(playlist.id)}
            onchange={() => onToggle(playlist.id)}
          />
          <span>{playlist.name}</span>
        </label>
      {/each}
    </div>
    <button type="submit">Subir y añadir</button>
  </form>
</div>
