<script>
  export let inviteCode;
  export let username;
  export let password;
  export let inviteUsername;
  export let invitePassword;
  export let inviteDisplayName;
  export let error;
  export let onActivateInvite;
  export let onLogin;
</script>

{#if inviteCode}
  <main class="login-shell">
    <form onsubmit={onActivateInvite}>
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
    <form onsubmit={(event) => onLogin(event)}>
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
