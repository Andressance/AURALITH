<script>
  export let playlistTitle;
  export let playlistShares;
  export let shareError;
  export let shareUsername;
  export let shareRole;
  export let onClose;
  export let onShare;
  export let onUpdateRole;
  export let onUnshare;
</script>

<div class="upload-playlist-picker share-panel" role="dialog" aria-modal="true" aria-label="Compartir playlist">
  <div class="sheet-heading">
    <strong>Compartir “{playlistTitle}”</strong>
    <button onclick={onClose}>×</button>
  </div>
  <p class="share-hint">Quien tenga acceso la verá en su biblioteca y podrá reproducirla. Con “Puede editar” también añade y quita canciones; el título, la portada y los accesos siguen siendo tuyos.</p>
  <form onsubmit={onShare}>
    <input bind:value={shareUsername} placeholder="Usuario" maxlength="63" />
    <select bind:value={shareRole} aria-label="Permiso">
      <option value="viewer">Solo lectura</option>
      <option value="editor">Puede editar</option>
    </select>
    <button type="submit">Dar acceso</button>
  </form>
  {#if shareError}<p class="error">{shareError}</p>{/if}
  <div class="share-list">
    {#each playlistShares as share}
      <div class="share-row">
        <span>{share.display_name || share.username}<small>@{share.username}</small></span>
        <div class="share-actions">
          <button class:active={share.role === "editor"} onclick={() => onUpdateRole(share)} title="Cambiar permiso">
            {share.role === "editor" ? "Puede editar" : "Solo lectura"}
          </button>
          <button onclick={() => onUnshare(share.user_id)} aria-label={`Quitar acceso a ${share.username}`}>Quitar</button>
        </div>
      </div>
    {:else}
      <p class="share-empty">Todavía no compartiste esta playlist.</p>
    {/each}
  </div>
</div>
