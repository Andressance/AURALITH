<script>
  import { tick } from "svelte";

  let authenticated = false;
  let username = "owner";
  let password = "";
  let tracks = [];
  let playlists = [];
  let sharePanelPlaylistId = null;
  let shareUsername = "";
  let shareRole = "viewer";
  let jamCode = "";
  let jamJoinCode = "";
  let jamState = null;
  let jamSocket = null;
  let jamError = "";
  let jamSearch = "";
  let devices = [];
  let devicesSocket = null;
  let devicesRetry = null;
  let remoteTargetId = null;
  let showDevicesPanel = false;
  let pendingLoad = null;
  const deviceId = (() => {
    try {
      const stored = sessionStorage.getItem("auralith_device_id");
      if (stored) return stored;
      const created = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
      sessionStorage.setItem("auralith_device_id", created);
      return created;
    } catch {
      return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
    }
  })();
  let playlistShares = [];
  let shareError = "";
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
  let savedVolume = Number(localStorage.getItem("auralith_volume") ?? 0.8);
  let volume = !Number.isNaN(savedVolume) && savedVolume >= 0 && savedVolume <= 1 ? savedVolume : 0.8;
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
  let dragOverPlaylistId = null;
  let newPlaylistName = "";
  let playerVisible = false;
  let pullDistance = 0;
  let pullStart = 0;
  let pulling = false;
  let refreshing = false;
  let playbackQueue = [];
  let shuffleMode = false;
  let loopMode = "off";
  let showQueuePanel = false;
  let csvPlaylistName = "";
  let csvImporting = false;
  let csvImportReport = null;
  let showUploadPlaylistPicker = false;
  let pendingUploadFiles = [];
  let uploadPlaylistIds = [];
  let uploadNewPlaylistName = "";
  let ownerUsers = [];
  let ownerInvitations = [];
  let invitationName = "";
  let invitationCode = "";
  let inviteCode = window.location.pathname.startsWith("/invite/")
    ? window.location.pathname.split("/invite/")[1]
    : "";
  let inviteUsername = "";
  let invitePassword = "";
  let inviteDisplayName = "";
  const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

  function viewFromPath() {
    const path = window.location.pathname;
    if (path.startsWith("/profile")) return "profile";
    if (path.startsWith("/playlists")) return "playlists";
    if (path.startsWith("/jam")) return "jam";
    return "library";
  }

  let activeView = viewFromPath();

  function navigateView(view) {
    const path = view === "library" ? "/" : `/${view}`;
    if (window.location.pathname !== path) {
      history.pushState({ view }, "", path);
    }
    activeView = view;
    if (view !== "library") {
      selectedPlaylistId = null;
      selectedPlaylist = null;
    }
  }

  window.addEventListener("popstate", () => {
    activeView = viewFromPath();
  });

  function focusedControlUsesSpace() {
    const element = document.activeElement;
    if (!element || element === document.body) return false;
    if (element.isContentEditable) return true;
    if (["TEXTAREA", "SELECT"].includes(element.tagName)) return true;
    if (element.tagName === "INPUT") {
      // Sliders do nothing with Space; text, checkbox and file inputs do.
      return (element.getAttribute("type") || "text").toLowerCase() !== "range";
    }
    return Boolean(
      element.closest("button, a[href], [role='button'], [role='switch'], [role='checkbox'], [role='tab']")
    );
  }

  window.addEventListener("keydown", (event) => {
    if (event.code !== "Space" || event.repeat || event.defaultPrevented || !currentTrack) return;
    // The focused play button activates itself on Space, so handling the key here as
    // well toggled playback twice. Let any control that consumes Space keep it.
    if (focusedControlUsesSpace()) return;
    event.preventDefault();
    togglePlayback();
  });

  function text(value, fallback = "") {
    return typeof value === "string" ? value : fallback;
  }

  function streamUrl(track) {
    // Media URLs are signed by the API and the session token is no longer accepted
    // in the query string, so there is no unauthenticated URL to build here.
    if (!track?.stream_url) return undefined;
    return `${API_BASE}${track.stream_url}`;
  }

  function assetUrl(path) {
    if (!path) return "";
    if (path.startsWith("http")) return path;
    return `${API_BASE}${path}`;
  }

  function titleInitial(title) {
    const value = text(title).trim();
    return value ? value.slice(0, 1).toUpperCase() : "♫";
  }

  function hideBrokenImage(event) {
    event.currentTarget.style.display = "none";
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

  async function activateInvite(event) {
    event.preventDefault();
    error = "";
    try {
      await api(`/api/invitations/${encodeURIComponent(inviteCode)}/activate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: inviteUsername,
          password: invitePassword,
          display_name: inviteDisplayName
        })
      });
      history.replaceState({}, "", "/");
      inviteCode = "";
      username = inviteUsername;
      password = invitePassword;
      await login();
    } catch (cause) {
      error = cause.message;
    }
  }

  async function login(event) {
    event?.preventDefault();
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
    if (profile.role === "owner") await loadOwnerUsers();
    resumeJam();
    connectDevicesSocket();
  }

  async function loadOwnerUsers() {
    ownerUsers = await api("/api/owner/users");
    ownerInvitations = await api("/api/owner/invitations");
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
    if (files.length > 1) {
      pendingUploadFiles = files;
      uploadPlaylistIds = [];
      uploadNewPlaylistName = "";
      showUploadPlaylistPicker = true;
      event.target.value = "";
      return;
    }
    await runUpload(files);
  }

  async function runUpload(files) {
    if (!files?.length) return;
    error = "";
    uploading = true;
    uploadQueue = files.map((file) => ({
      name: file.name,
      status: "pending",
      detail: "En cola"
    }));
    uploadProgress = `0 de ${files.length} completadas`;

    const uploadedTrackIds = [];
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
        if (uploadedTrack.id) uploadedTrackIds.push(uploadedTrack.id);
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
    if (uploadNewPlaylistName.trim() && uploadedTrackIds.length) {
      await api("/api/playlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: uploadNewPlaylistName.trim(), track_ids: uploadedTrackIds })
      });
    }
    for (const playlistId of uploadPlaylistIds) {
      if (uploadedTrackIds.length) {
        await api(`/api/playlists/${playlistId}/tracks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ track_ids: uploadedTrackIds })
        });
      }
    }
    uploadPlaylistIds = [];
    uploadNewPlaylistName = "";
    pendingUploadFiles = [];
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

  async function importPlaylistCsv(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const file = formElement.querySelector('input[type="file"]')?.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("name", csvPlaylistName);
    csvImporting = true;
    error = "";
    try {
      csvImportReport = await api("/api/playlists/import/csv", {
        method: "POST",
        body: form
      });
      csvPlaylistName = "";
      formElement.reset();
      await loadPlaylists();
    } catch (cause) {
      error = cause.message;
    } finally {
      csvImporting = false;
    }
  }

  async function confirmImportCandidate(result) {
    if (!csvImportReport || !result.candidate || result.confirmed) return;
    try {
      await api(`/api/playlists/${csvImportReport.playlist_id}/tracks/${result.candidate.id}`, {
        method: "POST"
      });
      csvImportReport = {
        ...csvImportReport,
        results: csvImportReport.results.map((item) =>
          item.row === result.row ? { ...item, confirmed: true } : item
        )
      };
    } catch (cause) {
      error = cause.message;
    }
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
    navigateView("library");
    selectedPlaylistId = playlist.id;
    if (!selectedPlaylist || selectedPlaylist.id !== playlist.id) {
      selectedPlaylist = {
        id: playlist.id,
        name: playlist.name,
        cover_url: playlist.cover_url || null,
        tracks: []
      };
    }
    const detail = await api(`/api/playlists/${playlist.id}`);
    if (selectedPlaylistId === playlist.id) {
      selectedPlaylist = detail;
    }
  }

  async function playPlaylist(playlist) {
    const detail = await api(`/api/playlists/${playlist.id}`);
    selectedPlaylistId = playlist.id;
    selectedPlaylist = detail;
    playbackQueue = detail.tracks || [];
    if (detail.tracks?.length) {
      play(detail.tracks[0]);
    }
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

  function openTrackPlaylistPicker(trackId) {
    selectedTrackIds = [trackId];
    showPlaylistPicker = true;
  }

  function startTrackDrag(event, trackId) {
    if (!selectedTrackIds.includes(trackId)) {
      selectedTrackIds = [trackId];
    }
    event.dataTransfer.effectAllowed = "copy";
    event.dataTransfer.setData("text/auralith-track", String(trackId));
  }

  function endTrackDrag() {
    dragOverPlaylistId = null;
  }

  function dragTrackOver(event, playlistId) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    dragOverPlaylistId = playlistId;
  }

  function leavePlaylistDrop(event) {
    if (!event.currentTarget.contains(event.relatedTarget)) {
      dragOverPlaylistId = null;
    }
  }

  async function dropTracksOnPlaylist(event, playlistId) {
    event.preventDefault();
    dragOverPlaylistId = null;
    await addSelectedToPlaylist(playlistId);
  }

  async function addSelectedToPlaylist(playlistId) {
    const toAdd = [...selectedTrackIds];
    if (!toAdd.length) return;
    selectedTrackIds = [];
    showPlaylistPicker = false;
    try {
      await api(`/api/playlists/${playlistId}/tracks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_ids: toAdd })
      });
      await loadPlaylists();
      if (selectedPlaylistId === playlistId) {
        selectedPlaylist = await api(`/api/playlists/${playlistId}`);
      }
    } catch (cause) {
      error = cause.message;
    }
  }

  async function createPlaylistWithSelection(event) {
    event.preventDefault();
    const name = newPlaylistName.trim();
    if (!name) return;
    const toAdd = [...selectedTrackIds];
    newPlaylistName = "";
    selectedTrackIds = [];
    showPlaylistPicker = false;
    try {
      await api("/api/playlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          track_ids: toAdd
        })
      });
      await loadPlaylists();
    } catch (cause) {
      error = cause.message;
    }
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
    clearTimeout(devicesRetry);
    if (devicesSocket) {
      devicesSocket.onclose = null;
      devicesSocket.close();
      devicesSocket = null;
    }
    devices = [];
    remoteTargetId = null;
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
      navigateView("library");
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

  async function createInvitation(event) {
    event.preventDefault();
    try {
      const invitation = await api("/api/owner/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: invitationName })
      });
      invitationCode = invitation.code;
      invitationName = "";
      await loadOwnerUsers();
    } catch (cause) {
      error = cause.message;
    }
  }

  async function copyInvitation() {
    if (!invitationCode) return;
    await navigator.clipboard?.writeText(`${window.location.origin}/invite/${invitationCode}`);
  }

  async function revokeInvitation(invitationId) {
    await api(`/api/owner/invitations/${invitationId}`, { method: "DELETE" });
    await loadOwnerUsers();
  }

  async function deleteGuest(account) {
    if (!window.confirm(`¿Eliminar la cuenta de ${account.display_name}? Se borrarán también sus canciones y playlists.`)) return;
    await api(`/api/owner/users/${account.id}`, { method: "DELETE" });
    await loadOwnerUsers();
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

  async function openSharePanel() {
    if (!selectedPlaylist?.id) return;
    sharePanelPlaylistId = selectedPlaylist.id;
    shareUsername = "";
    shareRole = "viewer";
    shareError = "";
    try {
      playlistShares = await api(`/api/playlists/${sharePanelPlaylistId}/shares`);
    } catch (cause) {
      shareError = cause.message;
      playlistShares = [];
    }
  }

  function closeSharePanel() {
    sharePanelPlaylistId = null;
    shareUsername = "";
    shareRole = "viewer";
    shareError = "";
    playlistShares = [];
  }

  async function sharePlaylist(event) {
    event.preventDefault();
    if (!sharePanelPlaylistId) return;
    shareError = "";
    try {
      await api(`/api/playlists/${sharePanelPlaylistId}/shares`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: shareUsername.trim(), role: shareRole })
      });
      shareUsername = "";
      playlistShares = await api(`/api/playlists/${sharePanelPlaylistId}/shares`);
    } catch (cause) {
      shareError = cause.message;
    }
  }

  async function unsharePlaylist(accountId) {
    if (!sharePanelPlaylistId) return;
    try {
      await api(`/api/playlists/${sharePanelPlaylistId}/shares/${accountId}`, { method: "DELETE" });
      playlistShares = await api(`/api/playlists/${sharePanelPlaylistId}/shares`);
    } catch (cause) {
      shareError = cause.message;
    }
  }

  async function updateShareRole(share) {
    if (!sharePanelPlaylistId) return;
    try {
      await api(`/api/playlists/${sharePanelPlaylistId}/shares/${share.user_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: share.role === "editor" ? "viewer" : "editor" })
      });
      playlistShares = await api(`/api/playlists/${sharePanelPlaylistId}/shares`);
    } catch (cause) {
      shareError = cause.message;
    }
  }

  async function togglePlaylistLibrary(playlist) {
    try {
      await api(`/api/playlists/${playlist.id}/library`, {
        method: playlist.saved ? "DELETE" : "POST"
      });
      await loadPlaylists();
      if (selectedPlaylist?.id === playlist.id) {
        selectedPlaylist = await api(`/api/playlists/${playlist.id}`);
      }
    } catch (cause) {
      error = cause.message;
    }
  }

  function connectJamSocket() {
    closeJamSocket();
    if (!jamCode) return;
    const base = API_BASE || window.location.origin;
    const socket = new WebSocket(`${base.replace(/^http/, "ws")}/ws/jam/${jamCode}`);
    jamSocket = socket;
    socket.onopen = () => socket.send(JSON.stringify({ token: sessionToken }));
    socket.onmessage = (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type === "state") {
        // The server sends the whole jam after every change, so the queue never drifts.
        jamState = message.state;
        applyJamPlayback(message.state);
      } else if (message.type === "participants") {
        jamState = { ...jamState, participants: message.participants };
      } else if (message.type === "ended") {
        leaveJamLocal();
        jamError = "El anfitrión terminó el jam";
      }
    };
    socket.onclose = () => {
      if (jamSocket === socket) jamSocket = null;
    };
  }

  function closeJamSocket() {
    if (!jamSocket) return;
    jamSocket.onclose = null;
    jamSocket.close();
    jamSocket = null;
  }

  function leaveJamLocal() {
    closeJamSocket();
    localStorage.removeItem("auralith_jam");
    jamCode = "";
    jamState = null;
  }

  async function resumeJam() {
    const stored = localStorage.getItem("auralith_jam");
    if (!stored) return;
    try {
      const result = await api("/api/jams/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: stored })
      });
      jamCode = result.code;
      jamState = result.state;
      connectJamSocket();
    } catch {
      localStorage.removeItem("auralith_jam");
    }
  }

  function leaveJam() {
    leaveJamLocal();
    if (audio) audio.pause();
  }

  async function applyJamPlayback(state) {
    const track = state?.current_track;
    if (!track) {
      if (audio && !audio.paused) audio.pause();
      return;
    }
    if (currentTrack?.id !== track.id) {
      await play(track);
    }
    if (!audio) return;
    const target = Number(state.position) || 0;
    if (Math.abs(audio.currentTime - target) > 1.5) audio.currentTime = target;
    if (state.is_playing) {
      audio.play().catch(() => {});
    } else if (!audio.paused) {
      audio.pause();
    }
  }

  async function createJam() {
    jamError = "";
    try {
      const result = await api("/api/jams", { method: "POST" });
      jamCode = result.code;
      localStorage.setItem("auralith_jam", result.code);
      jamState = result.state;
      connectJamSocket();
    } catch (cause) {
      jamError = cause.message;
    }
  }

  async function joinJam() {
    const code = jamJoinCode.trim().toUpperCase();
    if (!code) return;
    jamError = "";
    try {
      const result = await api("/api/jams/join", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code })
      });
      jamCode = result.code;
      localStorage.setItem("auralith_jam", result.code);
      jamJoinCode = "";
      jamState = result.state;
      connectJamSocket();
      applyJamPlayback(result.state);
    } catch (cause) {
      jamError = cause.message;
    }
  }

  async function jamControl(action, extra = {}) {
    if (!jamCode) return;
    try {
      await api(`/api/jams/${jamCode}/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, ...extra })
      });
    } catch (cause) {
      jamError = cause.message;
    }
  }

  async function jamQueueTrack(track, front = false) {
    if (!jamCode) return;
    try {
      await api(`/api/jams/${jamCode}/queue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ track_id: track.id, front })
      });
    } catch (cause) {
      jamError = cause.message;
    }
  }

  async function jamMoveQueueItem(item, direction) {
    if (!jamCode) return;
    try {
      await api(`/api/jams/${jamCode}/queue/${item.id}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ direction })
      });
    } catch (cause) {
      jamError = cause.message;
    }
  }

  function jamLibrary(query, library) {
    const needle = query.trim().toLowerCase();
    if (!needle) return library;
    return library.filter((track) =>
      [track.title, track.artist, track.album].some((value) => String(value || "").toLowerCase().includes(needle))
    );
  }

  async function jamRemoveQueueItem(item) {
    if (!jamCode) return;
    try {
      await api(`/api/jams/${jamCode}/queue/${item.id}`, { method: "DELETE" });
    } catch (cause) {
      jamError = cause.message;
    }
  }

  async function endJam() {
    if (!jamCode) return;
    try {
      await api(`/api/jams/${jamCode}/end`, { method: "POST" });
    } catch (cause) {
      jamError = cause.message;
    }
    leaveJam();
  }

  async function downloadBackup() {
    try {
      // A relative URL would hit the web origin, not the API, and a new tab cannot
      // carry the bearer token, so fetch the archive and save it as a blob.
      const headers = new Headers();
      if (sessionToken) headers.set("Authorization", `Bearer ${sessionToken}`);
      const response = await fetch(`${API_BASE}/api/backup`, { headers, credentials: "include" });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "No se pudo crear la copia de seguridad");
      }
      const disposition = response.headers.get("Content-Disposition") || "";
      const filename = /filename="?([^";]+)"?/.exec(disposition)?.[1] || "auralith-backup.zip";
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
      error = "";
    } catch (cause) {
      error = cause.message;
    }
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

  async function play(track) {
    if (!track?.stream_url) {
      error = "No se pudo reproducir la canción";
      return;
    }
    if (!playbackQueue.some((item) => item.id === track.id)) {
      playbackQueue = selectedPlaylist?.tracks?.length
        ? selectedPlaylist.tracks
        : visibleTracks.length
          ? visibleTracks
          : tracks;
    }
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
    await tick();
    if (audio) {
      audio.volume = volume;
      audio.load();
      try {
        await audio.play();
      } catch {
        isPlaying = false;
      }
    }
  }

  function togglePlayback() {
    if (jamCode) {
      jamControl(jamState?.is_playing ? "pause" : "play", { position: audio?.currentTime || 0 });
      return;
    }
    if (!audio) return;
    if (audio.paused) {
      audio.play();
      playerVisible = true;
    } else {
      audio.pause();
    }
  }

  function getNextQueueIndex() {
    if (!playbackQueue.length) return -1;
    if (shuffleMode) {
      if (playbackQueue.length === 1) return 0;
      const currentIndex = playbackQueue.findIndex((track) => track.id === currentTrack?.id);
      const candidates = playbackQueue
        .map((_, index) => index)
        .filter((index) => index !== currentIndex);
      return candidates[Math.floor(Math.random() * candidates.length)];
    }
    const currentIndex = playbackQueue.findIndex((track) => track.id === currentTrack?.id);
    return currentIndex >= 0 ? (currentIndex + 1) % playbackQueue.length : 0;
  }

  function playNext() {
    if (jamCode) {
      jamControl("next");
      return;
    }
    const index = getNextQueueIndex();
    if (index >= 0) play(playbackQueue[index]);
  }

  // Every play button goes through here, so a jam never plays something its members cannot hear.
  function playTrack(track) {
    if (jamCode) {
      jamControl("play", { track_id: track.id, position: 0 });
      return;
    }
    play(track);
  }

  function playPrevious() {
    if (jamCode) {
      jamControl("seek", { position: 0 });
      return;
    }
    if (!playbackQueue.length) return;
    if (audio?.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    const currentIndex = playbackQueue.findIndex((track) => track.id === currentTrack?.id);
    const index = currentIndex > 0 ? currentIndex - 1 : playbackQueue.length - 1;
    play(playbackQueue[index]);
  }

  function toggleShuffle() {
    shuffleMode = !shuffleMode;
  }

  function enqueueTrack(track, front = false) {
    if (jamCode) {
      jamQueueTrack(track, front);
      return;
    }
    if (!front && playbackQueue.some((item) => item.id === track.id)) return;
    const others = playbackQueue.filter((item) => item.id !== track.id);
    const currentIndex = others.findIndex((item) => item.id === currentTrack?.id);
    if (front && currentIndex >= 0) others.splice(currentIndex + 1, 0, track);
    else others.push(track);
    playbackQueue = others;
    if (!currentTrack) play(track);
  }

  function removeQueuedTrack(trackId) {
    playbackQueue = playbackQueue.filter((track) => track.id !== trackId);
  }

  function cycleLoopMode() {
    loopMode = loopMode === "off" ? "all" : loopMode === "all" ? "one" : "off";
  }

  function handleTrackEnded() {
    if (jamCode) {
      // Every member's player reports the end; the server advances only once.
      jamControl("next", { expected_track_id: currentTrack?.id });
      return;
    }
    if (loopMode === "one") {
      if (audio) {
        audio.currentTime = 0;
        audio.play();
      }
      return;
    }
    const currentIndex = playbackQueue.findIndex((track) => track.id === currentTrack?.id);
    if (loopMode === "all" || currentIndex < playbackQueue.length - 1) {
      playNext();
    }
  }

  function toggleUploadPlaylist(playlistId) {
    uploadPlaylistIds = uploadPlaylistIds.includes(playlistId)
      ? uploadPlaylistIds.filter((id) => id !== playlistId)
      : [...uploadPlaylistIds, playlistId];
  }

  async function confirmUploadPlaylist() {
    showUploadPlaylistPicker = false;
    await runUpload(pendingUploadFiles);
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
    try {
      localStorage.setItem("auralith_volume", String(volume));
    } catch {}
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
      ? [{ src: assetUrl(track.cover_url), sizes: "512x512", type: "image/webp" }]
      : [{ src: `${window.location.origin}/icon.svg`, sizes: "any", type: "image/svg+xml" }];
    navigator.mediaSession.metadata = new MediaMetadata({
      title: text(track.title, "Canción sin título"),
      artist: text(track.artist, "Auralith"),
      album: text(track.album, "Auralith"),
      artwork
    });
    syncMediaSession();
  }

  // Windows reads playbackState and position from the Media Session to draw the taskbar
  // controls of an installed PWA, so keep them in step with the audio element.
  function syncMediaSession() {
    if (!("mediaSession" in navigator)) return;
    navigator.mediaSession.playbackState = audio && !audio.paused ? "playing" : "paused";
    if (audio && Number.isFinite(audio.duration) && audio.duration > 0) {
      try {
        navigator.mediaSession.setPositionState({
          duration: audio.duration,
          playbackRate: audio.playbackRate || 1,
          position: Math.min(audio.currentTime, audio.duration)
        });
      } catch {}
    }
  }

  // Handlers are registered once, so the taskbar buttons keep working across track changes.
  function setupMediaSession() {
    if (!("mediaSession" in navigator)) return;
    const actions = {
      play: () => {
        if (jamCode ? !jamState?.is_playing : audio?.paused) togglePlayback();
      },
      pause: () => {
        if (jamCode ? jamState?.is_playing : !audio?.paused) togglePlayback();
      },
      previoustrack: playPrevious,
      nexttrack: playNext,
      seekto: (details) => {
        if (audio && Number.isFinite(details.seekTime)) audio.currentTime = details.seekTime;
      },
      seekbackward: () => {
        if (audio) audio.currentTime = Math.max(0, audio.currentTime - 10);
      },
      seekforward: () => {
        if (audio) audio.currentTime = Math.min(duration || Infinity, audio.currentTime + 10);
      }
    };
    for (const [action, handler] of Object.entries(actions)) {
      try {
        navigator.mediaSession.setActionHandler(action, handler);
      } catch {
        // Some browsers do not support every action; the others still work.
      }
    }
  }

  // Devices: each signed-in tab reports what it plays and can receive commands from the others.
  function describeDevice() {
    const ua = navigator.userAgent;
    const os = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Mac OS/.test(ua) ? "Mac" : "Linux";
    const browser = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "Navegador";
    const installed = window.matchMedia?.("(display-mode: standalone)").matches ? " · app" : "";
    return `${os} · ${browser}${installed}`;
  }

  function connectDevicesSocket() {
    clearTimeout(devicesRetry);
    if (devicesSocket) {
      devicesSocket.onclose = null;
      devicesSocket.close();
    }
    const base = API_BASE || window.location.origin;
    const socket = new WebSocket(`${base.replace(/^http/, "ws")}/ws/devices`);
    devicesSocket = socket;
    socket.onopen = () => socket.send(JSON.stringify({ token: sessionToken, device_id: deviceId, name: describeDevice() }));
    socket.onmessage = (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type === "devices") {
        devices = message.devices;
        if (remoteTargetId && !devices.some((device) => device.device_id === remoteTargetId)) remoteTargetId = null;
      } else if (message.type === "relay") {
        handleRelay(message.from, message.message);
      }
    };
    socket.onclose = () => {
      if (devicesSocket !== socket) return;
      devicesSocket = null;
      devices = [];
      remoteTargetId = null;
      if (authenticated) devicesRetry = setTimeout(connectDevicesSocket, 4000);
    };
  }

  function publishPresence() {
    if (devicesSocket?.readyState !== WebSocket.OPEN) return;
    devicesSocket.send(JSON.stringify({
      type: "presence",
      is_playing: Boolean(audio && !audio.paused),
      position: audio?.currentTime || 0,
      track: currentTrack
        ? { id: currentTrack.id, title: currentTrack.title, artist: currentTrack.artist, cover_url: currentTrack.cover_url }
        : null
    }));
  }

  function sendRelay(target, message) {
    if (devicesSocket?.readyState !== WebSocket.OPEN) return;
    devicesSocket.send(JSON.stringify({ type: "relay", target, message }));
  }

  async function handleRelay(from, message) {
    if (!message || typeof message !== "object") return;
    switch (message.cmd) {
      case "play":
        if (audio?.paused && currentTrack) audio.play();
        break;
      case "pause":
        audio?.pause();
        break;
      case "next":
        playNext();
        break;
      case "prev":
        playPrevious();
        break;
      case "seek":
        if (audio) audio.currentTime = Number(message.position) || 0;
        break;
      case "handoff":
        // The device that wants the music takes over: send it our track and stop here.
        if (!currentTrack || !audio) break;
        sendRelay(from, { cmd: "load", track: currentTrack, position: audio.currentTime, playing: !audio.paused });
        audio.pause();
        break;
      case "load":
        loadRemote(message);
        break;
    }
  }

  async function loadRemote(message) {
    const track = message.track;
    if (!track?.stream_url) return;
    if (currentTrack?.id === track.id && audio) {
      audio.currentTime = Number(message.position) || 0;
      if (message.playing) audio.play();
      else audio.pause();
      return;
    }
    pendingLoad = message;
    await play(track);
  }

  function controlDevice(action) {
    if (remoteTargetId) sendRelay(remoteTargetId, { cmd: action });
  }

  function toggleRemoteTarget(device) {
    remoteTargetId = remoteTargetId === device.device_id ? null : device.device_id;
  }

  function takeOverPlayback(device) {
    // The playing device answers with its track; see the "handoff" case above.
    sendRelay(device.device_id, { cmd: "handoff" });
  }

  setupMediaSession();
  setInterval(publishPresence, 5000);

  load().catch(() => {});
</script>

{#if !authenticated}
  {#if inviteCode}
    <main class="login-shell">
      <form onsubmit={activateInvite}>
        <div class="login-brand">
          <img src="/auralith-logo.svg" alt="Auralith" />
          <img class="login-wave" src="/auralith-wave.svg" alt="" aria-hidden="true" />
        </div>
        <h1>Crea tu cuenta</h1>
        <p>Te han invitado a una biblioteca privada.</p>
        <label>
          Nombre visible
          <input bind:value={inviteDisplayName} maxlength="100" autocomplete="name" />
        </label>
        <label>
          Usuario
          <input bind:value={inviteUsername} maxlength="63" autocomplete="username" />
        </label>
        <label>
          Contraseña
          <input type="password" bind:value={invitePassword} autocomplete="new-password" />
        </label>
        {#if error}<p class="error">{error}</p>{/if}
        <button type="submit">Crear cuenta</button>
      </form>
    </main>
  {:else}
    <main class="login-shell">
      <form onsubmit={(event) => login(event)}>
        <div class="login-brand">
          <img src="/auralith-logo.svg" alt="Auralith" />
          <img class="login-wave" src="/auralith-wave.svg" alt="" aria-hidden="true" />
        </div>
        <h1>Bienvenido de nuevo</h1>
        <p>Tu música. Tu servidor. Tus reglas.</p>
        <label>
          Usuario
          <input bind:value={username} autocomplete="username" />
        </label>
        <label>
          Contraseña
          <input type="password" bind:value={password} autocomplete="current-password" />
        </label>
        {#if error}<p class="error">{error}</p>{/if}
        <button type="submit">Entrar</button>
      </form>
    </main>
  {/if}
{:else}
  <div class="app-shell" class:player-visible={playerVisible}>
    <aside class="sidebar">
      <a class="brand" href="/" aria-label="Auralith">
        <img src="/icon.svg" alt="" />
        <h1>Auralith</h1>
      </a>
      <nav>
        <button class="nav-item" class:active={activeView === "library"} onclick={() => { navigateView("library"); visibleTracks = tracks; }}>⌂ <span>Inicio</span></button>
        <button class="nav-item" onclick={() => { navigateView("library"); searchQuery = ""; search(); }}>⌕ <span>Buscar</span></button>
        <button class="nav-item" class:active={activeView === "playlists"} onclick={() => navigateView("playlists")}>♫ <span>Playlists</span></button>
        <button class="nav-item" class:active={activeView === "profile"} onclick={() => navigateView("profile")}>● <span>Perfil</span></button>
        <button class="nav-item" class:active={activeView === "jam"} onclick={() => navigateView("jam")}>◉ <span>Jam</span></button>
        <button class="nav-item" class:active={showDevicesPanel} onclick={() => showDevicesPanel = !showDevicesPanel}>◫ <span>Dispositivos</span></button>
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
        {#each playlists.filter((playlist) => !playlist.shared || playlist.saved) as playlist}
          <div
            class="playlist-item"
            class:selected={selectedPlaylistId === playlist.id}
            class:drop-target={dragOverPlaylistId === playlist.id}
            role="group"
            aria-label={`Playlist ${playlist.name}`}
            ondragover={(event) => dragTrackOver(event, playlist.id)}
            ondragleave={leavePlaylistDrop}
            ondrop={(event) => dropTracksOnPlaylist(event, playlist.id)}
          >
            <button class="playlist-open" onclick={() => selectPlaylist(playlist)}>
              {#if playlist.cover_url}
                <img class="playlist-cover" src={assetUrl(playlist.cover_url)} alt="" loading="lazy" decoding="async" />
              {:else}
                <span class="playlist-cover">♫</span>
              {/if}
              <span><strong>{playlist.name}</strong><small>{playlist.shared ? `De ${playlist.owner}` : "Playlist"}</small></span>
            </button>
            <button
              class="playlist-play"
              onclick={(event) => { event.stopPropagation(); playPlaylist(playlist); }}
              aria-label={`Reproducir playlist ${playlist.name}`}
              title={`Reproducir ${playlist.name}`}
            >
              ▶
            </button>
          </div>
        {/each}
      </div>
      <div class="sidebar-footer">
        <button class="profile-button" onclick={() => navigateView("profile")}>
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
      onclick={() => navigateView("profile")}
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
      {#if activeView === "jam"}
        <section class="jam-page">
          <header class="jam-header">
            <div><span>Escuchar juntos</span><h2>Jam</h2></div>
            {#if jamCode}
              <button class="jam-leave" onclick={leaveJam}>Salir</button>
            {/if}
          </header>

          {#if jamError}<p class="error">{jamError}</p>{/if}

          {#if !jamCode}
            <div class="jam-start">
              <article class="jam-card">
                <strong>Crea un jam</strong>
                <p>Comparte el código y escuchad lo mismo a la vez. Cualquiera puede cambiar de canción.</p>
                <button class="primary-upload" onclick={createJam}>Crear jam</button>
              </article>
              <article class="jam-card">
                <strong>Entrar en un jam</strong>
                <p>Pide el código a quien lo haya creado.</p>
                <form onsubmit={(event) => { event.preventDefault(); joinJam(); }}>
                  <input bind:value={jamJoinCode} placeholder="Código" maxlength="12" />
                  <button type="submit">Entrar</button>
                </form>
              </article>
            </div>
          {:else}
            <div class="jam-code">
              <span>Código del jam</span>
              <strong>{jamCode}</strong>
              <button onclick={() => navigator.clipboard?.writeText(jamCode)}>Copiar</button>
            </div>

            <div class="jam-now">
              <div class="jam-cover">
                {#if jamState?.current_track?.cover_url}
                  <img src={assetUrl(jamState.current_track.cover_url)} alt="" />
                {:else}
                  ♫
                {/if}
              </div>
              <div class="jam-now-text">
                <span>{jamState?.is_playing ? "Sonando ahora" : jamState?.current_track ? "En pausa" : "Nada sonando"}</span>
                <strong>{jamState?.current_track ? text(jamState.current_track.title, "Canción sin título") : "Elige una canción"}</strong>
                <small>{jamState?.current_track ? text(jamState.current_track.artist, "Artista desconocido") : "Pulsa ▶ en la biblioteca de abajo para empezar a sonar todos a la vez"}</small>
              </div>
              <div class="jam-controls">
                <button onclick={() => jamControl(jamState?.is_playing ? "pause" : "play", { position: audio?.currentTime || 0 })} disabled={!jamState?.current_track}>
                  {jamState?.is_playing ? "Ⅱ Pausar" : "▶ Reproducir"}
                </button>
                <button onclick={() => jamControl("next")} disabled={!jamState?.queue?.length}>⏭ Siguiente</button>
              </div>
            </div>

            <div class="jam-people">
              {#each jamState?.participants || [] as person}
                <span class="jam-person">{person.display_name || person.username}{person.id === jamState.host_user_id ? " · anfitrión" : ""}</span>
              {/each}
            </div>

            <div class="jam-columns">
              <section class="jam-panel">
                <h3>A continuación <small>{jamState?.queue?.length || 0}</small></h3>
                <p class="jam-hint">La primera de la lista es la siguiente. Ordénalas con ↑ ↓.</p>
                {#each jamState?.queue || [] as item, index (item.id)}
                  <div class="jam-row">
                    <span>{text(item.track.title, "Canción sin título")}<small>{text(item.track.artist, "Artista desconocido")}</small></span>
                    <div class="jam-row-actions">
                      <button onclick={() => jamMoveQueueItem(item, "up")} disabled={index === 0} aria-label="Subir">↑</button>
                      <button onclick={() => jamMoveQueueItem(item, "down")} disabled={index === jamState.queue.length - 1} aria-label="Bajar">↓</button>
                      <button onclick={() => jamRemoveQueueItem(item)} aria-label="Quitar de la cola">Quitar</button>
                    </div>
                  </div>
                {:else}
                  <p class="jam-empty">Nada en cola. Cuando termine la canción, el jam pasará a la siguiente de aquí.</p>
                {/each}
              </section>
              <section class="jam-panel">
                <h3>Biblioteca</h3>
                <input class="jam-search" type="search" bind:value={jamSearch} placeholder="Buscar canción o artista" aria-label="Buscar en tu biblioteca" />
                {#each jamLibrary(jamSearch, tracks) as track (track.id)}
                  <div class="jam-row">
                    <span>{text(track.title, "Canción sin título")}<small>{text(track.artist, "Artista desconocido")}</small></span>
                    <div class="jam-row-actions">
                      <button onclick={() => playTrack(track)} aria-label={`Reproducir ${text(track.title, "canción")} ahora`}>▶ Ahora</button>
                      <button onclick={() => enqueueTrack(track, true)} aria-label={`Poner ${text(track.title, "canción")} la siguiente`}>⏭ Siguiente</button>
                      <button onclick={() => enqueueTrack(track)} aria-label={`Añadir ${text(track.title, "canción")} al final`}>+ Cola</button>
                    </div>
                  </div>
                {:else}
                  <p class="jam-empty">{tracks.length ? "Ninguna canción coincide con la búsqueda." : "Sube música para añadirla."}</p>
                {/each}
              </section>
            </div>

            {#if profile && jamState?.host_user_id === profile.id}
              <button class="jam-end" onclick={endJam}>Terminar el jam</button>
            {/if}
          {/if}
        </section>
      {/if}
      {#if activeView === "profile"}
        <section class="profile-page">
          <button class="page-back" onclick={() => navigateView("library")}><span>←</span> Volver a la biblioteca</button>
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
              <button type="button" class="profile-cancel" onclick={() => navigateView("library")}>Cancelar</button>
              <button type="submit" class="profile-save">Guardar cambios</button>
            </div>
          </form>
          <section class="profile-account-actions">
            <div>
              <span>Cuenta y datos</span>
              <p>Gestiona tu sesión y las copias locales de la biblioteca.</p>
            </div>
            <div class="profile-action-grid">
              {#if profile?.role === "owner"}
                <button type="button" onclick={downloadBackup}>
                  <span>↧</span>
                  <strong>Copia de seguridad</strong>
                </button>
                <label>
                  <span>↥</span>
                  <strong>Restaurar</strong>
                  <input type="file" accept=".zip" onchange={restoreBackup} />
                </label>
              {/if}
              <button type="button" class="danger" onclick={logout}>
                <span>⏻</span>
                <strong>Cerrar sesión</strong>
              </button>
            </div>
          </section>
          {#if profile?.role === "owner"}
            <section class="user-management">
              <div class="user-management-heading">
                <div>
                  <span>Administración</span>
                  <h2>Usuarios</h2>
                  <p>Crea invitaciones y gestiona las cuentas de esta instancia.</p>
                </div>
              </div>
              <form class="invitation-form" onsubmit={createInvitation}>
                <input bind:value={invitationName} maxlength="100" placeholder="Nombre del invitado (opcional)" />
                <button type="submit">Crear invitación</button>
              </form>
              {#if invitationCode}
                <div class="invitation-link">
                  <div>
                    <span>Enlace nuevo</span>
                    <strong>{window.location.origin}/invite/{invitationCode}</strong>
                  </div>
                  <button onclick={copyInvitation}>Copiar</button>
                </div>
              {/if}
              <div class="user-list">
                {#each ownerUsers as account}
                  <article>
                    <div class="user-avatar">{account.display_name.slice(0, 1).toUpperCase()}</div>
                    <div class="user-details">
                      <strong>{account.display_name}</strong>
                      <span>@{account.username} · {account.role === "owner" ? "Propietario" : "Invitado"}</span>
                    </div>
                    {#if account.role !== "owner"}
                      <button class="danger" onclick={() => deleteGuest(account)} title="Eliminar cuenta">×</button>
                    {/if}
                  </article>
                {/each}
              </div>
              {#if ownerInvitations.length}
                <div class="pending-invitations">
                  <strong>Invitaciones pendientes</strong>
                  {#each ownerInvitations as invitation}
                    {#if !invitation.used}
                      <article>
                        <div>
                          <strong>{invitation.display_name || "Invitado"}</strong>
                          <span>Caduca {new Date(invitation.expires_at).toLocaleDateString()}</span>
                        </div>
                        <button onclick={() => revokeInvitation(invitation.id)} title="Revocar invitación">Revocar</button>
                      </article>
                    {/if}
                  {/each}
                </div>
              {/if}
            </section>
          {/if}
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
          <form class="csv-import-form" onsubmit={importPlaylistCsv}>
            <div>
              <strong>Importar desde CSV</strong>
              <span>Se añadirán automáticamente solo coincidencias exactas.</span>
            </div>
            <input bind:value={csvPlaylistName} maxlength="200" placeholder="Nombre de la playlist (opcional)" />
            <input type="file" accept=".csv,text/csv" required />
            <button type="submit" disabled={csvImporting}>
              {csvImporting ? "Importando…" : "Importar CSV"}
            </button>
          </form>
          {#if csvImportReport}
            <section class="csv-import-report" aria-live="polite">
              <div>
                <strong>{csvImportReport.playlist_name}</strong>
                <span>{csvImportReport.added} coincidencias exactas añadidas</span>
              </div>
              <button onclick={() => csvImportReport = null} aria-label="Cerrar informe">×</button>
              {#each csvImportReport.results as result}
                <article>
                  <div>
                    <strong>{result.title}</strong>
                    <span>{result.artist || "Artista desconocido"} · {result.status.replaceAll("_", " ")}</span>
                    {#if result.candidate}
                      <small>Sugerencia: {result.candidate.title} — {result.candidate.artist || "Artista desconocido"}</small>
                    {/if}
                  </div>
                  {#if result.candidate && !result.confirmed && result.status !== "EXACT"}
                    <button onclick={() => confirmImportCandidate(result)}>Añadir</button>
                  {:else if result.confirmed}
                    <span class="csv-import-confirmed">Añadida</span>
                  {/if}
                </article>
              {/each}
            </section>
          {/if}
          <div class="playlist-grid">
            {#each playlists as playlist}
              <article class="playlist-card">
                <button class="playlist-card-open" onclick={() => { navigateView("library"); selectPlaylist(playlist); }}>
                {#if playlist.cover_url}
                  <img src={assetUrl(playlist.cover_url)} alt="" />
                {:else}
                  <span>♫</span>
                {/if}
                <strong>{playlist.name}</strong>
                <small>{playlist.shared ? `De ${playlist.owner}${playlist.role === "editor" ? " · colaboras" : ""}` : "Playlist"}</small>
                </button>
                {#if playlist.shared}
                  <button class="playlist-library" class:saved={playlist.saved} onclick={() => togglePlaylistLibrary(playlist)}>
                    {playlist.saved ? "✓ En tu biblioteca" : "＋ Añadir a mi biblioteca"}
                  </button>
                {/if}
                <button
                  class="playlist-card-play"
                  onclick={() => playPlaylist(playlist)}
                  aria-label={`Reproducir playlist ${playlist.name}`}
                  title={`Reproducir ${playlist.name}`}
                >▶</button>
              </article>
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
          <label class="search-box">
            <span aria-hidden="true">⌕</span>
            <input class="search" bind:value={searchQuery} oninput={search} placeholder="¿Qué quieres reproducir?" />
          </label>
        </header>
      {/if}

      {#if activeView === "library" && selectedPlaylist}
        <section class="playlist-hero">
          <div class="hero-cover">
            {#if selectedPlaylist.cover_url}
              <img src={assetUrl(selectedPlaylist.cover_url)} alt="" fetchpriority="low" loading="lazy" decoding="async" onerror={hideBrokenImage} />
            {:else}
              ♫
            {/if}
            {#if selectedPlaylist.role === "owner"}
              <label title="Cambiar foto">✎<input type="file" accept="image/jpeg,image/png,image/webp" onchange={uploadPlaylistCover} /></label>
            {/if}
          </div>
          <div>
            <span>{selectedPlaylist.role === "owner" ? "Playlist" : selectedPlaylist.role === "editor" ? "Colaboras en esta playlist" : "Compartida contigo"}</span>
            <h2>{selectedPlaylist.name}</h2>
            <p>{selectedPlaylist.shared ? `De ${selectedPlaylist.owner}` : "Auralith"} · {selectedPlaylist.tracks.length} canciones</p>
            <div class="hero-actions">
              {#if selectedPlaylist.role === "owner"}
                <button class="share-playlist" onclick={openSharePanel}>Compartir</button>
              {:else}
                <button class="share-playlist" onclick={() => togglePlaylistLibrary(selectedPlaylist)}>
                  {selectedPlaylist.saved ? "Quitar de mi biblioteca" : "Añadir a mi biblioteca"}
                </button>
              {/if}
            </div>
          </div>
        </section>
        <section class="track-list playlist-tracks">
          {#each selectedPlaylist.tracks as track, index}
            <article
              class:playing={currentTrack?.id === track.id}
              draggable="true"
              ondragstart={(event) => startTrackDrag(event, track.id)}
              ondragend={endTrackDrag}
            >
              <span class="track-index">{index + 1}</span>
              <button class="track-play" onclick={() => playTrack(track)}>{currentTrack?.id === track.id && isPlaying ? "Ⅱ" : "▶"}</button>
              <div><strong>{text(track.title, "Canción sin título")}</strong><span>{text(track.artist, "Artista desconocido")}</span></div>
              <button class="row-action" onclick={() => enqueueTrack(track, true)} title="Reproducir después" aria-label="Reproducir después">⏭</button>
              <button class="row-action" onclick={() => enqueueTrack(track)} title="Añadir a la cola" aria-label="Añadir a la cola">＋</button>
              {#if selectedPlaylist.role !== "viewer"}
                <button class="row-action" onclick={() => removeFromPlaylist(track)} title="Quitar">×</button>
              {/if}
            </article>
          {/each}
        </section>
      {:else if activeView === "library"}
        <section class="library-header">
          <div><span>Tu música</span><h2>Made for you</h2></div>
          <label class="primary-upload" class:disabled={uploading}>Subir canciones<input type="file" multiple accept=".mp3,.flac,audio/mpeg,audio/flac" onchange={upload} disabled={uploading} /></label>
        </section>
        <section class="track-grid">
          {#each visibleTracks as track}
            <article
              class:playing={currentTrack?.id === track.id}
              draggable="true"
              ondragstart={(event) => startTrackDrag(event, track.id)}
              ondragend={endTrackDrag}
            >
              <label class="track-select">
                <input
                  type="checkbox"
                  checked={selectedTrackIds.includes(track.id)}
                  onchange={() => toggleTrackSelection(track.id)}
                  aria-label={`Seleccionar ${text(track.title, "Canción")}`}
                />
              </label>
              <button class="cover" onclick={() => playTrack(track)} aria-label={`Reproducir ${text(track.title, "Canción sin título")}`}>
                {#if track.cover_url}
                  <img src={assetUrl(track.cover_url)} alt="" loading="lazy" decoding="async" onerror={hideBrokenImage} />
                {:else}
                  <span>{titleInitial(track.title)}</span>
                {/if}
                <b>{currentTrack?.id === track.id && isPlaying ? "Ⅱ" : "▶"}</b>
              </button>
              <strong>{text(track.title, "Canción sin título")}</strong>
              <span>{text(track.artist, "Artista desconocido")}</span>
              <div class="track-actions">
                <button onclick={() => enqueueTrack(track, true)} aria-label="Reproducir después" title="Reproducir después">⏭</button>
                <button onclick={() => enqueueTrack(track)} aria-label="Añadir a la cola" title="Añadir a la cola">↗</button>
                <button onclick={() => openTrackPlaylistPicker(track.id)} aria-label="Añadir a playlist" title="Añadir a playlist">＋</button>
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
              <img src={assetUrl(currentTrack.cover_url)} alt="" onerror={hideBrokenImage} />
            {:else}
              ♫
            {/if}
          </div>
          <div><strong>{text(currentTrack.title, "Canción sin título")}</strong><span>{text(currentTrack.artist, "Artista desconocido")}</span></div>
        </div>
        <div class="player-center">
          <div class="player-controls">
            <button class:active={shuffleMode} onclick={toggleShuffle} aria-label="Aleatorio" title="Aleatorio">⇄</button>
            <button onclick={playPrevious} aria-label="Anterior" title="Anterior">↤</button>
            <button class="player-toggle" onclick={togglePlayback}>{isPlaying ? "Ⅱ" : "▶"}</button>
            <button onclick={playNext} aria-label="Siguiente" title="Siguiente">↦</button>
            <button class:active={showQueuePanel} onclick={() => showQueuePanel = !showQueuePanel} aria-label={`Cola de reproducción (${playbackQueue.length})`} title="Cola de reproducción">≡</button>
            <button class:active={loopMode !== "off"} onclick={cycleLoopMode} aria-label="Modo bucle" title={loopMode === "off" ? "Bucle desactivado" : loopMode === "all" ? "Repetir lista" : "Repetir canción"}>
              {loopMode === "one" ? "↻1" : "↻"}
            </button>
          </div>
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
          onplay={() => { isPlaying = true; syncMediaSession(); publishPresence(); }}
          onpause={() => { isPlaying = false; syncMediaSession(); publishPresence(); }}
          ontimeupdate={(event) => progress = event.currentTarget.currentTime}
          onloadedmetadata={(event) => {
            const element = event.currentTarget;
            duration = element.duration;
            if (pendingLoad) {
              element.currentTime = Number(pendingLoad.position) || 0;
              if (!pendingLoad.playing) element.pause();
              pendingLoad = null;
            }
            syncMediaSession();
          }}
          onvolumechange={(event) => volume = event.currentTarget.volume}
          onended={handleTrackEnded}
          onerror={() => { isPlaying = false; error = "No se pudo reproducir la canción"; }}
        ></audio>
      </footer>
    {/if}
    {#if showQueuePanel}
      <aside class="queue-panel" class:player-visible={playerVisible} aria-label="Cola de reproducción">
        <div class="queue-heading">
          <strong>Cola de reproducción</strong>
          <span>{playbackQueue.length} canciones</span>
          <button onclick={() => showQueuePanel = false} aria-label="Cerrar cola">×</button>
        </div>
        {#if currentTrack}
          <div class="queue-current"><small>Reproduciendo</small><strong>{currentTrack.title}</strong></div>
        {/if}
        {#each playbackQueue.filter((track) => track.id !== currentTrack?.id) as track}
          <article>
            <button onclick={() => playTrack(track)}>
              <strong>{track.title}</strong>
              <span>{track.artist || "Artista desconocido"}</span>
            </button>
            <button onclick={() => removeQueuedTrack(track.id)} aria-label={`Quitar ${track.title} de la cola`}>×</button>
          </article>
        {:else}
          <p>No hay canciones próximas en la cola.</p>
        {/each}
      </aside>
    {/if}
  </div>
  {#if showDevicesPanel}
    <aside class="queue-panel devices-panel" class:player-visible={playerVisible} aria-label="Dispositivos">
      <div class="queue-heading">
        <strong>Dispositivos</strong>
        <span>{devices.length} conectado(s)</span>
        <button onclick={() => showDevicesPanel = false} aria-label="Cerrar dispositivos">×</button>
      </div>
      <p>Mismo perfil, otros dispositivos. Elige cuál controlas o pásale la reproducción.</p>
      {#if !devicesSocket}
        <p>Conectando con tus dispositivos…</p>
      {/if}
      {#each devices as device (device.device_id)}
        {@const self = device.device_id === deviceId}
        <article class="device-card" class:controlling={remoteTargetId === device.device_id}>
          <div class="device-info">
            <strong>{device.name}{self ? " · este dispositivo" : ""}</strong>
            <span>{device.track ? `${device.is_playing ? "Sonando" : "En pausa"}: ${device.track.title}` : "Sin reproducción"}</span>
          </div>
          {#if !self}
            <div class="device-actions">
              <button onclick={() => toggleRemoteTarget(device)}>{remoteTargetId === device.device_id ? "Dejar de controlar" : "Controlar"}</button>
              {#if device.track}<button onclick={() => takeOverPlayback(device)}>Pasar aquí</button>{/if}
            </div>
          {/if}
        </article>
      {/each}
      {#if devicesSocket && devices.length < 2}
        <p class="jam-empty">Abre Auralith con esta cuenta en otro dispositivo y aparecerá aquí.</p>
      {/if}
      {#each devices.filter((device) => device.device_id === remoteTargetId) as target (target.device_id)}
        <div class="device-remote">
          <small>Controlando: {target.name}</small>
          <div class="jam-controls">
            <button onclick={() => controlDevice("prev")} aria-label="Anterior">⏮</button>
            <button onclick={() => controlDevice(target.is_playing ? "pause" : "play")}>{target.is_playing ? "Ⅱ Pausar" : "▶ Reproducir"}</button>
            <button onclick={() => controlDevice("next")} aria-label="Siguiente">⏭</button>
          </div>
        </div>
      {/each}
    </aside>
  {/if}
  {#if selectedTrackIds.length}
    <section class="selection-bar" class:player-visible={playerVisible}>
      <strong>{selectedTrackIds.length} seleccionada(s)</strong>
      <button onclick={() => showPlaylistPicker = true}>Añadir a playlist</button>
      <button class="selection-clear" onclick={() => selectedTrackIds = []}>Cancelar</button>
    </section>
  {/if}

  {#if showPlaylistPicker}
    <div class="playlist-picker" class:player-visible={playerVisible} role="dialog" aria-modal="true" aria-label="Añadir a playlist">
      <div class="sheet-heading">
        <strong>Añadir a una playlist</strong>
        <button onclick={() => showPlaylistPicker = false}>×</button>
      </div>
      <form onsubmit={createPlaylistWithSelection}>
        <input bind:value={newPlaylistName} placeholder="Nueva playlist" maxlength="200" />
        <button type="submit">Crear y añadir</button>
      </form>
      {#each playlists.filter((playlist) => !playlist.shared || playlist.role !== "viewer") as playlist}
        <button class="playlist-picker-item" onclick={() => addSelectedToPlaylist(playlist.id)}>
          {#if playlist.cover_url}
            <img src={assetUrl(playlist.cover_url)} alt="" loading="lazy" decoding="async" />
          {:else}
            <span>♫</span>
          {/if}
          <strong>{playlist.name}</strong>
        </button>
      {/each}
    </div>
  {/if}
  {#if sharePanelPlaylistId && selectedPlaylist}
    <div class="upload-playlist-picker share-panel" role="dialog" aria-modal="true" aria-label="Compartir playlist">
      <div class="sheet-heading">
        <strong>Compartir “{selectedPlaylist.name}”</strong>
        <button onclick={closeSharePanel}>×</button>
      </div>
      <p class="share-hint">Quien tenga acceso la verá en su biblioteca y podrá reproducirla. Con “Puede editar” también añade y quita canciones; el título, la portada y los accesos siguen siendo tuyos.</p>
      <form onsubmit={sharePlaylist}>
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
              <button class:active={share.role === "editor"} onclick={() => updateShareRole(share)} title="Cambiar permiso">
                {share.role === "editor" ? "Puede editar" : "Solo lectura"}
              </button>
              <button onclick={() => unsharePlaylist(share.user_id)} aria-label={`Quitar acceso a ${share.username}`}>Quitar</button>
            </div>
          </div>
        {:else}
          <p class="share-empty">Todavía no compartiste esta playlist.</p>
        {/each}
      </div>
    </div>
  {/if}
  {#if showUploadPlaylistPicker}
    <div class="upload-playlist-picker" role="dialog" aria-modal="true" aria-label="Añadir canciones al subir">
      <div class="sheet-heading">
        <strong>Añadir las {pendingUploadFiles.length} canciones a playlists</strong>
        <button onclick={() => { showUploadPlaylistPicker = false; pendingUploadFiles = []; }}>×</button>
      </div>
      <form onsubmit={(event) => { event.preventDefault(); confirmUploadPlaylist(); }}>
        <input bind:value={uploadNewPlaylistName} placeholder="Crear una nueva playlist" maxlength="200" />
        <div class="upload-playlist-options">
          {#each playlists.filter((playlist) => !playlist.shared || playlist.role !== "viewer") as playlist}
            <label>
              <input
                type="checkbox"
                checked={uploadPlaylistIds.includes(playlist.id)}
                onchange={() => toggleUploadPlaylist(playlist.id)}
              />
              <span>{playlist.name}</span>
            </label>
          {/each}
        </div>
        <button type="submit">Subir y añadir</button>
      </form>
    </div>
  {/if}
{/if}
