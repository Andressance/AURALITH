<script>
  export let count;
  export let playerVisible;
  export let onAddToPlaylist;
  export let onClear;
</script>

<section class="selection-bar" class:player-visible={playerVisible}>
  <strong>{count} seleccionada(s)</strong>
  <button onclick={onAddToPlaylist}>Añadir a playlist</button>
  <button class="selection-clear" onclick={onClear}>Cancelar</button>
</section>
