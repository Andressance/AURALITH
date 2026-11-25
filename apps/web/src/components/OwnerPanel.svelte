<script>
  export let invitationName;
  export let invitationCode;
  export let ownerUsers;
  export let ownerInvitations;
  export let onCreateInvitation;
  export let onCopyInvitation;
  export let onRevokeInvitation;
  export let onDeleteGuest;
</script>

<section class="user-management">
  <div class="user-management-heading">
    <div>
      <span>Administración</span>
      <h2>Usuarios</h2>
      <p>Crea invitaciones y gestiona las cuentas de esta instancia.</p>
    </div>
  </div>
  <form class="invitation-form" onsubmit={onCreateInvitation}>
    <input bind:value={invitationName} maxlength="100" placeholder="Nombre del invitado (opcional)" />
    <button type="submit">Crear invitación</button>
  </form>
  {#if invitationCode}
    <div class="invitation-link">
      <div>
        <span>Enlace nuevo</span>
        <strong>{window.location.origin}/invite/{invitationCode}</strong>
      </div>
      <button onclick={onCopyInvitation}>Copiar</button>
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
          <button class="danger" onclick={() => onDeleteGuest(account)} title="Eliminar cuenta">×</button>
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
            <button onclick={() => onRevokeInvitation(invitation.id)} title="Revocar invitación">Revocar</button>
          </article>
        {/if}
      {/each}
    </div>
  {/if}
</section>
