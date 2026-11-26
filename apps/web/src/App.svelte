<script>
  import { tick } from "svelte";
  import { API_BASE, assetUrl, text } from "./lib/format.js";
  import { artistKeyForName, artistName, buildArtistIndex, searchLibrary } from "./lib/library.js";
  import ArtistPage from "./components/ArtistPage.svelte";
  import DashboardPage from "./components/DashboardPage.svelte";
  import DevicesPanel from "./components/DevicesPanel.svelte";
  import JamPage from "./components/JamPage.svelte";
  import LoginView from "./components/LoginView.svelte";
  import NowPlayingView from "./components/NowPlayingView.svelte";
  import PlayerBar from "./components/PlayerBar.svelte";
  import PlaylistPicker from "./components/PlaylistPicker.svelte";
  import PlaylistsPage from "./components/PlaylistsPage.svelte";
  import PlaylistView from "./components/PlaylistView.svelte";
  import ProfilePage from "./components/ProfilePage.svelte";
  import QueuePanel from "./components/QueuePanel.svelte";
  import SearchResults from "./components/SearchResults.svelte";
  import SelectionBar from "./components/SelectionBar.svelte";
  import SharePanel from "./components/SharePanel.svelte";
  import Sidebar from "./components/Sidebar.svelte";
  import TrackGrid from "./components/TrackGrid.svelte";
  import UploadPanel from "./components/UploadPanel.svelte";
  import UploadPlaylistPicker from "./components/UploadPlaylistPicker.svelte";
  import WrappedPage from "./components/WrappedPage.svelte";

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

  $: artistIndex = buildArtistIndex(tracks);
  $: selectedArtist = artistIndex.find((artist) => artist.key === selectedArtistKey) || null;
  $: searchResults = searchQuery.trim()
    ? searchLibrary(tracks, searchQuery, artistIndex)
    : { artists: [], albums: [], tracks: [] };

  function viewFromPath() {
    const path = window.location.pathname;
    if (path.startsWith("/profile")) return "profile";
    if (path.startsWith("/playlists")) return "playlists";
    if (path.startsWith("/artist/")) return "artist";
    if (path.startsWith("/wrapped")) return "wrapped";
    if (path.startsWith("/stats")) return "stats";
    if (path.startsWith("/jam")) return "jam";
    return "library";
  }

  function artistKeyFromPath() {
    if (!window.location.pathname.startsWith("/artist/")) return null;
    const raw = window.location.pathname.slice("/artist/".length);
    try {
      return artistKeyForName(decodeURIComponent(raw));
    } catch {
      return artistKeyForName(raw);
    }
  }

  let activeView = viewFromPath();
  let selectedArtistKey = artistKeyFromPath();
  let selectedArtistAlbum = null;
  let selectedArtist = null;
  let artistIndex = [];
  let searchResults = { artists: [], albums: [], tracks: [] };
  let searchInput;
  let mainPanel;
  let nowPlayingOpen = false;
  let playCounts = loadPlayCounts();
  let wrapped = null;
  let wrappedYears = [];
  let wrappedYear = new Date().getFullYear();
  let wrappedLoading = false;
  let wrappedError = "";
  let statsOverview = null;
  let statsPeriod = "year";
  let statsLoading = false;
  let statsError = "";
  let dashboardWidgets = [];
  let dashboardSaving = false;
  let wrappedRequestId = 0;
  let statsRequestId = 0;
  let dashboardSaveId = 0;
  let dashboardSaveChain = Promise.resolve();
  let listenedTrack = null;
  let listenedSeconds = 0;
  let listenedAt = 0;

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
    if (view === "wrapped") loadWrapped(wrappedYear);
    if (view === "stats") loadStats(statsPeriod);
  }

  window.addEventListener("popstate", () => {
    activeView = viewFromPath();
    selectedArtistKey = artistKeyFromPath();
    nowPlayingOpen = false;
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

  function streamUrl(track) {
    // Media URLs are signed by the API and the session token is no longer accepted
    // in the query string, so there is no unauthenticated URL to build here.
    if (!track?.stream_url) return undefined;
    return `${API_BASE}${track.stream_url}`;
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
    if (activeView === "wrapped") await loadWrapped(wrappedYear);
    if (activeView === "stats") await loadStats(statsPeriod);
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
    // Opening a playlist leaves the search behind, so the results cannot hide it.
    searchQuery = "";
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
    // Send the last listening session before the session token stops working,
    // but never keep the user waiting on a dead connection.
    await Promise.race([
      flushListening(),
      new Promise((resolve) => setTimeout(resolve, 2000))
    ]);
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
    if (currentTrack?.id !== track.id) flushListening();
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
    recordPlay(track);
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
    flushListening();
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

  // State changes that child components ask for through callbacks.
  function goHome() {
    navigateView("library");
    searchQuery = "";
    selectedPlaylistId = null;
    selectedPlaylist = null;
    visibleTracks = tracks;
  }

  async function goSearch() {
    navigateView("library");
    await tick();
    searchInput?.focus();
  }

  function openArtist(name, album = null) {
    const resolved = typeof name === "string" && name.trim() ? name.trim() : "Artista desconocido";
    history.pushState({ view: "artist" }, "", `/artist/${encodeURIComponent(resolved)}`);
    selectedArtistKey = artistKeyForName(resolved);
    selectedArtistAlbum = album;
    activeView = "artist";
    nowPlayingOpen = false;
    if (mainPanel) mainPanel.scrollTop = 0;
  }

  function playCollection(collection) {
    const playable = (collection || []).filter((track) => track?.stream_url);
    if (!playable.length) return;
    playbackQueue = playable;
    play(playable[0]);
  }

  function loadPlayCounts() {
    try {
      return JSON.parse(localStorage.getItem("auralith_play_counts") || "{}") || {};
    } catch {
      return {};
    }
  }

  function recordPlay(track) {
    if (!track?.id) return;
    playCounts = { ...playCounts, [track.id]: (playCounts[track.id] || 0) + 1 };
    try {
      localStorage.setItem("auralith_play_counts", JSON.stringify(playCounts));
    } catch {}
  }

  async function toggleCurrentFavorite() {
    if (!currentTrack) return;
    const isFavorite = favorites.some((item) => item.id === currentTrack.id);
    try {
      await (isFavorite ? unfavorite(currentTrack) : favorite(currentTrack));
    } catch (cause) {
      error = cause.message;
    }
  }

  async function loadWrapped(year) {
    const request = ++wrappedRequestId;
    wrappedLoading = true;
    wrappedError = "";
    try {
      const years = await api("/api/stats/years");
      const result = await api(`/api/stats/wrapped?year=${encodeURIComponent(year)}`);
      // Changing the year quickly can make an older response arrive last.
      if (request !== wrappedRequestId) return;
      wrappedYears = years;
      wrapped = result;
      wrappedYear = result.year;
    } catch (cause) {
      if (request === wrappedRequestId) wrappedError = cause.message;
    } finally {
      if (request === wrappedRequestId) wrappedLoading = false;
    }
  }

  async function loadStats(period = statsPeriod) {
    const request = ++statsRequestId;
    statsLoading = true;
    statsError = "";
    try {
      const [overview, layout] = await Promise.all([
        api(`/api/stats/overview?period=${encodeURIComponent(period)}`),
        api("/api/stats/dashboard")
      ]);
      if (request !== statsRequestId) return;
      statsOverview = overview;
      statsPeriod = period;
      dashboardWidgets = layout.widgets || [];
    } catch (cause) {
      if (request === statsRequestId) statsError = cause.message;
    } finally {
      if (request === statsRequestId) statsLoading = false;
    }
  }

  // Layout writes are chained so two quick edits cannot reach the server out of
  // order and leave the older design stored. Only the newest answer is applied.
  function saveDashboardWidgets(widgets) {
    const request = ++dashboardSaveId;
    dashboardWidgets = widgets;
    dashboardSaving = true;
    statsError = "";
    dashboardSaveChain = dashboardSaveChain.then(async () => {
      try {
        const saved = await api("/api/stats/dashboard", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ widgets })
        });
        if (request === dashboardSaveId) dashboardWidgets = saved.widgets || widgets;
      } catch (cause) {
        if (request !== dashboardSaveId) return;
        statsError = cause.message;
        // Do not leave edits on screen that the server rejected.
        await loadStats(statsPeriod);
      } finally {
        if (request === dashboardSaveId) dashboardSaving = false;
      }
    });
    return dashboardSaveChain;
  }

  function resetDashboard() {
    const request = ++dashboardSaveId;
    dashboardSaving = true;
    statsError = "";
    dashboardSaveChain = dashboardSaveChain.then(async () => {
      try {
        const saved = await api("/api/stats/dashboard/reset", { method: "POST" });
        if (request === dashboardSaveId) dashboardWidgets = saved.widgets || [];
      } catch (cause) {
        if (request === dashboardSaveId) statsError = cause.message;
      } finally {
        if (request === dashboardSaveId) dashboardSaving = false;
      }
    });
    return dashboardSaveChain;
  }

  // Listening time is measured from the media element, so seeks and buffering do not
  // count as minutes. One report is sent per track session.
  function trackListening(element) {
    if (!currentTrack || element.paused) return;
    if (!listenedTrack || listenedTrack.id !== currentTrack.id) {
      flushListening();
      listenedTrack = currentTrack;
      listenedSeconds = 0;
      listenedAt = element.currentTime;
      return;
    }
    const delta = element.currentTime - listenedAt;
    listenedAt = element.currentTime;
    if (delta > 0 && delta <= 5) listenedSeconds += delta;
  }

  function flushListening({ keepalive = false } = {}) {
    const track = listenedTrack;
    const seconds = Math.round(listenedSeconds);
    listenedTrack = null;
    listenedSeconds = 0;
    listenedAt = 0;
    // Very short previews are noise, and the API rejects them anyway.
    if (!track || seconds < 5) return Promise.resolve();
    const headers = new Headers({ "Content-Type": "application/json" });
    if (sessionToken) headers.set("Authorization", `Bearer ${sessionToken}`);
    return fetch(`${API_BASE}/api/stats/plays`, {
      method: "POST",
      headers,
      credentials: "include",
      keepalive,
      body: JSON.stringify({ track_id: track.id, seconds })
    }).catch(() => {});
  }

  function closeUploadPlaylistPicker() {
    showUploadPlaylistPicker = false;
    pendingUploadFiles = [];
  }

  setupMediaSession();
  setInterval(publishPresence, 5000);

  // Keep the last partial session when the tab is hidden or closed.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) flushListening({ keepalive: true });
  });
  window.addEventListener("pagehide", () => flushListening({ keepalive: true }));

  load().catch(() => {});
</script>

{#if !authenticated}
  <LoginView
    {inviteCode}
    bind:username
    bind:password
    bind:inviteUsername
    bind:invitePassword
    bind:inviteDisplayName
    {error}
    onActivateInvite={activateInvite}
    onLogin={login}
  />
{:else}
  <div class="app-shell" class:player-visible={playerVisible}>
    <Sidebar
      {activeView}
      {showDevicesPanel}
      {playlists}
      {selectedPlaylistId}
      {dragOverPlaylistId}
      bind:playlistName
      {profile}
      {profileName}
      onNavigate={navigateView}
      onHome={goHome}
      onSearch={goSearch}
      onToggleDevices={() => showDevicesPanel = !showDevicesPanel}
      onUpload={upload}
      onCreatePlaylist={createPlaylist}
      onSelectPlaylist={selectPlaylist}
      onPlayPlaylist={playPlaylist}
      onDragOver={dragTrackOver}
      onDragLeave={leavePlaylistDrop}
      onDrop={dropTracksOnPlaylist}
    />

    <main
      class="main-panel"
      bind:this={mainPanel}
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
        <JamPage
          {jamCode}
          {jamState}
          {jamError}
          bind:jamJoinCode
          bind:jamSearch
          {tracks}
          {profile}
          onCreate={createJam}
          onJoin={joinJam}
          onLeave={leaveJam}
          onEnd={endJam}
          onTogglePlayback={togglePlayback}
          onControl={jamControl}
          onMoveQueueItem={jamMoveQueueItem}
          onRemoveQueueItem={jamRemoveQueueItem}
          onPlayTrack={playTrack}
          onEnqueue={enqueueTrack}
        />
      {/if}
      {#if activeView === "profile"}
        <ProfilePage
          {profile}
          bind:profileName
          bind:profileUsername
          bind:invitationName
          {invitationCode}
          {ownerUsers}
          {ownerInvitations}
          onNavigate={navigateView}
          onSave={saveProfile}
          onUploadAvatar={uploadProfileAvatar}
          onDownloadBackup={downloadBackup}
          onRestoreBackup={restoreBackup}
          onLogout={logout}
          onCreateInvitation={createInvitation}
          onCopyInvitation={copyInvitation}
          onRevokeInvitation={revokeInvitation}
          onDeleteGuest={deleteGuest}
        />
      {:else if activeView === "playlists"}
        <PlaylistsPage
          {playlists}
          bind:playlistName
          bind:csvPlaylistName
          {csvImporting}
          {csvImportReport}
          onCreatePlaylist={createPlaylist}
          onImportCsv={importPlaylistCsv}
          onCloseReport={() => csvImportReport = null}
          onConfirmCandidate={confirmImportCandidate}
          onNavigate={navigateView}
          onSelectPlaylist={selectPlaylist}
          onToggleLibrary={togglePlaylistLibrary}
          onPlayPlaylist={playPlaylist}
        />
      {/if}
      {#if uploadQueue.length}
        <UploadPanel {uploadQueue} {uploading} {uploadProgress} onClose={() => uploadQueue = []} />
      {/if}
      {#if activeView === "library"}
        <header class="topbar">
          <label class="search-box">
            <span aria-hidden="true">⌕</span>
            <input class="search" bind:this={searchInput} bind:value={searchQuery} placeholder="¿Qué quieres reproducir?" />
          </label>
          {#if searchQuery.trim()}
            <button class="search-clear" onclick={() => searchQuery = ""} aria-label="Limpiar búsqueda" title="Limpiar búsqueda">×</button>
          {/if}
        </header>
      {/if}

      {#if activeView === "library" && searchQuery.trim()}
        <SearchResults
          results={searchResults}
          {currentTrack}
          {isPlaying}
          onPlayTrack={playTrack}
          onPlayCollection={playCollection}
          onEnqueue={enqueueTrack}
          onOpenArtist={openArtist}
        />
      {:else if activeView === "library" && selectedPlaylist}
        <PlaylistView
          {selectedPlaylist}
          {currentTrack}
          {isPlaying}
          onOpenArtist={openArtist}
          onUploadCover={uploadPlaylistCover}
          onShare={openSharePanel}
          onToggleLibrary={togglePlaylistLibrary}
          onPlayTrack={playTrack}
          onEnqueue={enqueueTrack}
          onRemove={removeFromPlaylist}
          onDragStart={startTrackDrag}
          onDragEnd={endTrackDrag}
        />
      {:else if activeView === "library"}
        <TrackGrid
          {visibleTracks}
          {currentTrack}
          {isPlaying}
          {selectedTrackIds}
          {uploading}
          onUpload={upload}
          onPlayTrack={playTrack}
          onEnqueue={enqueueTrack}
          onOpenPlaylistPicker={openTrackPlaylistPicker}
          onFavorite={favorite}
          onDelete={deleteTrack}
          onToggleSelection={toggleTrackSelection}
          onDragStart={startTrackDrag}
          onDragEnd={endTrackDrag}
          onOpenArtist={openArtist}
        />
      {:else if activeView === "stats"}
        <DashboardPage
          overview={statsOverview}
          widgets={dashboardWidgets}
          period={statsPeriod}
          loading={statsLoading || (!statsOverview && !statsError)}
          error={statsError}
          saving={dashboardSaving}
          onChangePeriod={loadStats}
          onSaveWidgets={saveDashboardWidgets}
          onResetWidgets={resetDashboard}
          onOpenArtist={openArtist}
        />
      {:else if activeView === "wrapped"}
        <WrappedPage
          {wrapped}
          years={wrappedYears}
          year={wrappedYear}
          loading={wrappedLoading || (!wrapped && !wrappedError)}
          error={wrappedError}
          onChangeYear={loadWrapped}
          onOpenArtist={openArtist}
        />
      {:else if activeView === "artist"}
        {#if selectedArtist}
          <ArtistPage
            artist={selectedArtist}
            {currentTrack}
            {isPlaying}
            {playCounts}
            initialAlbum={selectedArtistAlbum}
            onBack={() => navigateView("library")}
            onPlayTrack={playTrack}
            onPlayCollection={playCollection}
            onEnqueue={enqueueTrack}
          />
        {:else if tracks.length}
          <section class="empty-state">
            <h2>Artista no encontrado</h2>
            <p>Ese artista ya no tiene canciones en esta biblioteca.</p>
            <button onclick={() => navigateView("library")}>Volver a la biblioteca</button>
          </section>
        {/if}
      {/if}
    </main>

    {#if currentTrack && playerVisible}
      <PlayerBar
        {currentTrack}
        {isPlaying}
        {shuffleMode}
        {loopMode}
        {showQueuePanel}
        queueLength={playbackQueue.length}
        {progress}
        {duration}
        {volume}
        onToggleShuffle={toggleShuffle}
        onPrevious={playPrevious}
        onTogglePlayback={togglePlayback}
        onNext={playNext}
        onToggleQueue={() => showQueuePanel = !showQueuePanel}
        onCycleLoop={cycleLoopMode}
        onSeek={seek}
        onVolume={changeVolume}
        onOpenNowPlaying={() => nowPlayingOpen = true}
      >
        <audio
          bind:this={audio}
          autoplay
          preload="metadata"
          src={streamUrl(currentTrack)}
          onplay={() => { isPlaying = true; syncMediaSession(); publishPresence(); }}
          onpause={() => { isPlaying = false; syncMediaSession(); publishPresence(); }}
          ontimeupdate={(event) => {
            progress = event.currentTarget.currentTime;
            trackListening(event.currentTarget);
          }}
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
      </PlayerBar>
    {/if}
    {#if nowPlayingOpen && currentTrack}
      <NowPlayingView
        {currentTrack}
        {isPlaying}
        {progress}
        {duration}
        {volume}
        {shuffleMode}
        {loopMode}
        favorite={favorites.some((item) => item.id === currentTrack.id)}
        queueLength={playbackQueue.length}
        onClose={() => nowPlayingOpen = false}
        onTogglePlayback={togglePlayback}
        onPrevious={playPrevious}
        onNext={playNext}
        onToggleShuffle={toggleShuffle}
        onCycleLoop={cycleLoopMode}
        onSeek={seek}
        onVolume={changeVolume}
        onToggleQueue={() => showQueuePanel = !showQueuePanel}
        onToggleFavorite={toggleCurrentFavorite}
        onOpenArtist={() => openArtist(artistName(currentTrack))}
      />
    {/if}
    {#if showQueuePanel}
      <QueuePanel
        {playbackQueue}
        {currentTrack}
        {playerVisible}
        raised={nowPlayingOpen}
        onClose={() => showQueuePanel = false}
        onPlayTrack={playTrack}
        onRemove={removeQueuedTrack}
      />
    {/if}
  </div>
  {#if showDevicesPanel}
    <DevicesPanel
      {devices}
      connected={Boolean(devicesSocket)}
      {deviceId}
      {remoteTargetId}
      {playerVisible}
      onClose={() => showDevicesPanel = false}
      onToggleRemoteTarget={toggleRemoteTarget}
      onTakeOver={takeOverPlayback}
      onControl={controlDevice}
    />
  {/if}
  {#if selectedTrackIds.length}
    <SelectionBar
      count={selectedTrackIds.length}
      {playerVisible}
      onAddToPlaylist={() => showPlaylistPicker = true}
      onClear={() => selectedTrackIds = []}
    />
  {/if}

  {#if showPlaylistPicker}
    <PlaylistPicker
      {playlists}
      bind:newPlaylistName
      {playerVisible}
      onClose={() => showPlaylistPicker = false}
      onCreateWithSelection={createPlaylistWithSelection}
      onAddToPlaylist={addSelectedToPlaylist}
    />
  {/if}
  {#if sharePanelPlaylistId && selectedPlaylist}
    <SharePanel
      playlistTitle={selectedPlaylist.name}
      {playlistShares}
      {shareError}
      bind:shareUsername
      bind:shareRole
      onClose={closeSharePanel}
      onShare={sharePlaylist}
      onUpdateRole={updateShareRole}
      onUnshare={unsharePlaylist}
    />
  {/if}
  {#if showUploadPlaylistPicker}
    <UploadPlaylistPicker
      fileCount={pendingUploadFiles.length}
      {playlists}
      bind:uploadNewPlaylistName
      {uploadPlaylistIds}
      onClose={closeUploadPlaylistPicker}
      onToggle={toggleUploadPlaylist}
      onConfirm={confirmUploadPlaylist}
    />
  {/if}
{/if}
