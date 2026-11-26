<script>
  import { assetUrl, hideBrokenImage } from "../lib/format.js";

  export let widget;
  export let overview = null;
  export let onOpenArtist;

  const WEEKDAYS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
  const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
  const COLORS = ["#b58aff", "#8256ff", "#5a35c9", "#9c78ff", "#6a3ff0", "#3b2a6e"];

  function formatValue(value) {
    if (widget.metric === "plays") {
      return `${value} ${value === 1 ? "reproducción" : "reproducciones"}`;
    }
    const minutes = Math.round(Number(value) || 0);
    if (minutes < 60) return `${minutes} min`;
    return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
  }

  function buildRows(widget, overview) {
    if (!overview) return [];
    switch (widget.dimension) {
      case "hours":
        return (overview.hourly || []).map((item) => ({
          label: item.hour % 3 === 0 ? `${String(item.hour).padStart(2, "0")}h` : "",
          title: `${String(item.hour).padStart(2, "0")}:00`,
          seconds: item.seconds,
          plays: item.plays
        }));
      case "weekdays":
        return (overview.weekday || []).map((item) => ({
          label: WEEKDAYS[item.weekday] || "?",
          seconds: item.seconds,
          plays: item.plays
        }));
      case "months":
        return (overview.monthly || []).map((item) => ({
          label: MONTHS[item.month - 1] || "?",
          seconds: item.seconds,
          plays: item.plays
        }));
      case "artists":
        return (overview.top_artists || []).map((item) => ({
          label: item.name,
          artist: item.name,
          seconds: item.seconds,
          plays: item.plays,
          cover: item.cover_url
        }));
      case "tracks":
        return (overview.top_tracks || []).map((item) => ({
          label: item.title,
          artist: item.artist,
          sublabel: item.artist,
          seconds: item.seconds,
          plays: item.plays,
          cover: item.cover_url
        }));
      case "albums":
        return (overview.top_albums || []).map((item) => ({
          label: item.name,
          artist: item.artist,
          sublabel: item.artist,
          seconds: item.seconds,
          plays: item.plays,
          cover: item.cover_url
        }));
      case "genres":
        return (overview.top_genres || []).map((item) => ({
          label: item.name,
          seconds: item.seconds,
          plays: item.plays
        }));
      default:
        return [];
    }
  }

  // Reading widget and overview here (not only inside the function) makes the
  // reactive statement depend on them; otherwise the chart keeps its first data.
  $: rows = widget && overview ? buildRows(widget, overview) : [];
  $: chartRows = rows.map((row, index) => ({
    ...row,
    value: widget.metric === "plays" ? Number(row.plays) || 0 : Math.round((Number(row.seconds) || 0) / 60)
  }));
  $: visibleRows = chartRows.filter((row) => row.value > 0);
  $: totalValue = chartRows.reduce((sum, row) => sum + row.value, 0);
  $: maxValue = Math.max(1, ...chartRows.map((row) => row.value));
  // Rankings always show the biggest entries; columns keep calendar order.
  $: rankedRows = [...visibleRows].sort((a, b) => b.value - a.value);
  $: barRows = rankedRows.slice(0, 8);
  $: listRows = rankedRows.slice(0, 6);
  $: donutRows = rankedRows.slice(0, 5);
  $: donutTotal = donutRows.reduce((sum, row) => sum + row.value, 0);
  $: restValue = Math.max(0, totalValue - donutTotal);
  $: statRow =
    widget.dimension === "total"
      ? {
          label: "Tu tiempo total",
          value: widget.metric === "plays" ? overview?.totals?.plays || 0 : overview?.totals?.minutes || 0
        }
      : rankedRows[0] || null;
  $: donutStyle = (() => {
    let cursor = 0;
    const parts = [];
    for (const [index, row] of donutRows.entries()) {
      const share = donutTotal ? (row.value / donutTotal) * 100 : 0;
      parts.push(`${COLORS[index % COLORS.length]} ${cursor}% ${cursor + share}%`);
      cursor += share;
    }
    if (cursor < 100) parts.push(`rgba(181, 138, 255, 0.16) ${cursor}% 100%`);
    return `conic-gradient(${parts.join(", ")})`;
  })();
</script>

<article class="stat-widget" class:wide={widget.type === "columns"}>
  <header class="stat-widget-head">
    <h3>{widget.title}</h3>
    <span>{widget.metric === "plays" ? "Reproducciones" : "Minutos"}</span>
  </header>

  {#if totalValue === 0 && widget.dimension !== "total"}
    <p class="stat-widget-empty">Sin datos en este periodo.</p>
  {:else if widget.type === "stat" || widget.dimension === "total"}
    {#if statRow}
      <div class="stat-big">
        <strong>{formatValue(statRow.value)}</strong>
        <span>{statRow.title || statRow.label}</span>
        <small>{overview?.totals?.plays || 0} reproducciones · {overview?.totals?.unique_artists || 0} artistas</small>
      </div>
    {/if}
  {:else if widget.type === "columns"}
    <div class="stat-columns">
      {#each chartRows as row}
        <span class="stat-column" title={`${row.title || row.label}: ${formatValue(row.value)}`}>
          <span class="stat-column-bar" style={`height: ${Math.max(4, Math.round((row.value / maxValue) * 100))}%`}></span>
          <small>{row.label}</small>
        </span>
      {/each}
    </div>
  {:else if widget.type === "donut"}
    <div class="stat-donut-wrap">
      <div class="stat-donut" style={`background: ${donutStyle}`}></div>
      <div class="stat-legend">
        {#each donutRows as row, index}
          <span>
            <i style={`background: ${COLORS[index % COLORS.length]}`}></i>
            <span class="stat-legend-label">{row.label}</span>
            <small>{formatValue(row.value)}</small>
          </span>
        {/each}
        {#if restValue > 0}
          <span><i style="background: rgba(181, 138, 255, 0.16)"></i><span class="stat-legend-label">Otros</span><small>{formatValue(restValue)}</small></span>
        {/if}
      </div>
    </div>
  {:else if widget.type === "list"}
    <div class="stat-list">
      {#each listRows as row, index}
        <article>
          <span class="stat-list-rank">{index + 1}</span>
          <span class="stat-list-cover">
            {#if row.cover}
              <img src={assetUrl(row.cover)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
            {:else}
              ♫
            {/if}
          </span>
          <span class="stat-list-copy">
            {#if row.artist}
              <button onclick={() => onOpenArtist(row.artist)}>{row.title || row.label}</button>
            {:else}
              <strong>{row.title || row.label}</strong>
            {/if}
            {#if row.sublabel}<small>{row.sublabel}</small>{/if}
          </span>
          <strong class="stat-list-value">{formatValue(row.value)}</strong>
        </article>
      {/each}
    </div>
  {:else}
    <div class="stat-bars">
      {#each barRows as row}
        <article>
          <span class="stat-bar-label">
            {#if row.artist}
              <button onclick={() => onOpenArtist(row.artist)}>{row.title || row.label}</button>
            {:else}
              <strong>{row.title || row.label}</strong>
            {/if}
            <small>{formatValue(row.value)}</small>
          </span>
          <span class="stat-bar-track">
            <span style={`width: ${Math.max(4, Math.round((row.value / maxValue) * 100))}%`}></span>
          </span>
        </article>
      {/each}
    </div>
  {/if}
</article>
