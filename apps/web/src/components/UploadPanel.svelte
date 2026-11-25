<script>
  export let uploadQueue;
  export let uploading;
  export let uploadProgress;
  export let onClose;
</script>

<section class="upload-panel" aria-live="polite">
  <div class="upload-summary">
    <div>
      <strong>{uploading ? "Subiendo canciones" : "Subida finalizada"}</strong>
      <span>{uploadProgress}</span>
    </div>
    {#if !uploading}
      <button onclick={onClose} aria-label="Cerrar resumen">×</button>
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
