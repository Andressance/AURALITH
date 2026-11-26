<script>
  import { assetUrl } from "../lib/format.js";
  import OwnerPanel from "./OwnerPanel.svelte";

  export let profile;
  export let profileName;
  export let profileUsername;
  export let invitationName;
  export let invitationCode;
  export let ownerUsers;
  export let ownerInvitations;
  export let onNavigate;
  export let onSave;
  export let onUploadAvatar;
  export let historyStatus;
  export let historyBusy;
  export let onDownloadBackup;
  export let onRestoreBackup;
  export let onExportHistory;
  export let onDeleteHistory;
  export let onLogout;
  export let onCreateInvitation;
  export let onCopyInvitation;
  export let onRevokeInvitation;
  export let onDeleteGuest;
</script>

<section class="profile-page">
  <button class="page-back" onclick={() => onNavigate("library")}><span>←</span> Volver a la biblioteca</button>
  <div class="profile-hero">
    <div class="profile-avatar-large">
      {#if profile?.avatar_url}
        <img src={assetUrl(profile.avatar_url)} alt="" />
      {:else}
        <span>{profileName.slice(0, 1).toUpperCase()}</span>
      {/if}
      <label title="Cambiar foto">✎<input type="file" accept="image/jpeg,image/png,image/webp" onchange={onUploadAvatar} /></label>
    </div>
    <div class="profile-heading">
      <span>Perfil</span>
      <h2>{profileName}</h2>
      <p>@{profileUsername} · {profile?.role === "owner" ? "Propietario" : "Invitado"}</p>
    </div>
  </div>
  <form class="profile-form" onsubmit={onSave}>
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
      <button type="button" class="profile-cancel" onclick={() => onNavigate("library")}>Cancelar</button>
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
        <button type="button" onclick={onDownloadBackup}>
          <span>↧</span>
          <strong>Copia de seguridad</strong>
        </button>
        <label>
          <span>↥</span>
          <strong>Restaurar</strong>
          <input type="file" accept=".zip" onchange={onRestoreBackup} />
        </label>
      {/if}
      <button type="button" class="danger" onclick={onLogout}>
        <span>⏻</span>
        <strong>Cerrar sesión</strong>
      </button>
    </div>
  </section>
  <section class="profile-account-actions">
    <div>
      <span>Historial de escucha</span>
      <p>Alimenta tus estadísticas y el Wrapped. Puedes descargarlo en CSV o borrar las escuchas antiguas.</p>
    </div>
    <div class="history-actions">
      <button type="button" onclick={onExportHistory} disabled={historyBusy}>
        ↧ Exportar historial en CSV
      </button>
      <div class="history-delete">
        <button type="button" onclick={() => onDeleteHistory(90)} disabled={historyBusy}>Borrar +90 días</button>
        <button type="button" onclick={() => onDeleteHistory(365)} disabled={historyBusy}>Borrar +1 año</button>
        <button type="button" class="danger" onclick={() => onDeleteHistory(0)} disabled={historyBusy}>Borrar todo</button>
      </div>
      {#if historyStatus}
        <p class="history-status" role="status">{historyStatus}</p>
      {/if}
    </div>
  </section>
  {#if profile?.role === "owner"}
    <OwnerPanel
      bind:invitationName
      {invitationCode}
      {ownerUsers}
      {ownerInvitations}
      {onCreateInvitation}
      {onCopyInvitation}
      {onRevokeInvitation}
      {onDeleteGuest}
    />
  {/if}
</section>
