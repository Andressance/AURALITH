<script>
  import StatsWidget from "./StatsWidget.svelte";

  export let overview = null;
  export let widgets = [];
  export let period = "year";
  export let loading = false;
  export let error = "";
  export let saving = false;
  export let onChangePeriod;
  export let onSaveWidgets;
  export let onResetWidgets;
  export let onOpenArtist;

  const PERIODS = [
    { value: "year", label: "Este año" },
    { value: "month", label: "Este mes" },
    { value: "all", label: "Todo" }
  ];
  const DIMENSIONS = [
    { value: "hours", label: "Horas del día" },
    { value: "weekdays", label: "Días de la semana" },
    { value: "months", label: "Meses" },
    { value: "artists", label: "Artistas" },
    { value: "tracks", label: "Canciones" },
    { value: "albums", label: "Álbumes" },
    { value: "genres", label: "Géneros" },
    { value: "total", label: "Totales" }
  ];
  const TYPES = [
    { value: "bars", label: "Barras" },
    { value: "columns", label: "Columnas" },
    { value: "donut", label: "Dona" },
    { value: "list", label: "Lista" },
    { value: "stat", label: "Número grande" }
  ];
  const MAX_WIDGETS = 12;

  let editing = false;
  // Start from the layout the parent already has: this component remounts when you
  // come back to the dashboard, and the prop is populated by then.
  let localWidgets = widgets.map((widget) => ({ ...widget }));
  let lastWidgets = widgets;
  let newDimension = "artists";
  let newType = "bars";
  let newMetric = "minutes";

  $: if (widgets !== lastWidgets) {
    lastWidgets = widgets;
    localWidgets = widgets.map((widget) => ({ ...widget }));
  }
  $: maxWidgetsReached = localWidgets.length >= MAX_WIDGETS;

  function formatMinutes(minutes) {
    const value = Math.round(Number(minutes) || 0);
    if (value < 60) return `${value} min`;
    return `${Math.floor(value / 60)} h ${value % 60} min`;
  }

  function commit(next) {
    localWidgets = next;
    onSaveWidgets(next);
  }

  function addWidget() {
    commit([
      ...localWidgets,
      {
        id: `w${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
        title: "",
        type: newDimension === "total" ? "stat" : newType,
        dimension: newDimension,
        metric: newMetric
      }
    ]);
  }

  function removeWidget(widgetId) {
    commit(localWidgets.filter((widget) => widget.id !== widgetId));
  }

  function renameWidget(widgetId, title) {
    commit(
      localWidgets.map((widget) =>
        widget.id === widgetId ? { ...widget, title: title.slice(0, 80) } : widget
      )
    );
  }

  function moveWidget(index, direction) {
    const target = index + direction;
    if (target < 0 || target >= localWidgets.length) return;
    const next = [...localWidgets];
    [next[index], next[target]] = [next[target], next[index]];
    commit(next);
  }
</script>

<section class="stats-page">
  <header class="stats-heading">
    <div>
      <span>Tu música en números</span>
      <h2>Estadísticas</h2>
    </div>
    <div class="stats-actions">
      <button class="stats-edit" class:active={editing} onclick={() => editing = !editing}>
        {editing ? "Listo" : "Editar"}
      </button>
      {#if editing}
        <button class="stats-reset" onclick={onResetWidgets}>Restablecer</button>
      {/if}
    </div>
  </header>

  <div class="stats-period" role="group" aria-label="Periodo de las estadísticas">
    {#each PERIODS as option}
      <button class:active={period === option.value} onclick={() => onChangePeriod(option.value)}>{option.label}</button>
    {/each}
    {#if overview?.label}<span>{overview.label}</span>{/if}
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  <section class="stats-totals" aria-label="Totales del periodo">
    <article>
      <span>Minutos</span>
      <strong>{formatMinutes(overview?.totals?.minutes || 0)}</strong>
    </article>
    <article>
      <span>Reproducciones</span>
      <strong>{overview?.totals?.plays || 0}</strong>
    </article>
    <article>
      <span>Artistas</span>
      <strong>{overview?.totals?.unique_artists || 0}</strong>
    </article>
    <article>
      <span>Canciones</span>
      <strong>{overview?.totals?.unique_tracks || 0}</strong>
    </article>
    <article>
      <span>Géneros</span>
      <strong>{overview?.totals?.unique_genres || 0}</strong>
    </article>
  </section>

  {#if loading}
    <p class="wrapped-status">Cargando estadísticas…</p>
  {:else}
    <div class="stats-grid">
      {#each localWidgets as widget, index (widget.id)}
        <div class="stats-cell" class:wide={widget.type === "columns"}>
          <StatsWidget {widget} {overview} {onOpenArtist} />
          {#if editing}
            <div class="stats-widget-toolbar">
              <input
                value={widget.title}
                onchange={(event) => renameWidget(widget.id, event.currentTarget.value)}
                aria-label="Título del gráfico"
                maxlength="80"
              />
              <div>
                <button onclick={() => moveWidget(index, -1)} disabled={index === 0} aria-label="Mover antes">↑</button>
                <button onclick={() => moveWidget(index, 1)} disabled={index === localWidgets.length - 1} aria-label="Mover después">↓</button>
                <button onclick={() => removeWidget(widget.id)} aria-label="Quitar gráfico">×</button>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>

    {#if !localWidgets.length}
      <p class="search-empty">No hay gráficos. Añade uno para empezar.</p>
    {/if}

    {#if editing}
      <form class="stats-add" onsubmit={(event) => { event.preventDefault(); addWidget(); }}>
        <strong>Añadir gráfico</strong>
        <label>
          Desglose
          <select bind:value={newDimension}>
            {#each DIMENSIONS as option}<option value={option.value}>{option.label}</option>{/each}
          </select>
        </label>
        <label>
          Tipo
          <select bind:value={newType} disabled={newDimension === "total"}>
            {#each TYPES as option}<option value={option.value}>{option.label}</option>{/each}
          </select>
        </label>
        <label>
          Medida
          <select bind:value={newMetric}>
            <option value="minutes">Minutos</option>
            <option value="plays">Reproducciones</option>
          </select>
        </label>
        <button type="submit" disabled={maxWidgetsReached}>Añadir</button>
        {#if maxWidgetsReached}<small>Máximo {MAX_WIDGETS} gráficos.</small>{/if}
      </form>
    {/if}
  {/if}

  <p class="stats-save">{saving ? "Guardando…" : "Tu diseño se guarda en tu cuenta."}</p>
</section>
