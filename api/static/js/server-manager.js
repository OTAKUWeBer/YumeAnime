class ServerManager {
  constructor() {
    this.storageKey = 'yumePreferredServer';
    this.preferredServer = this.loadPreferredServer();
  }

  loadPreferredServer() {
    try {
      return localStorage.getItem(this.storageKey) || 'hd-1';
    } catch (error) {
      console.error('Error loading preferred server:', error);
      return 'hd-1';
    }
  }

  savePreferredServer(serverName) {
    try {
      localStorage.setItem(this.storageKey, serverName);
      this.preferredServer = serverName;
      console.log(`Preferred server saved: ${serverName}`);
    } catch (error) {
      console.error('Error saving preferred server:', error);
    }
  }

  getPreferredServer() {
    return this.preferredServer;
  }

  isServerAvailable(serverName, availableServers) {
    if (!availableServers || availableServers.length === 0) {
      return false;
    }
    return availableServers.some(s => s.serverName === serverName);
  }

  selectBestServer(availableServers) {
    if (!availableServers || availableServers.length === 0) {
      return 'hd-1';
    }

    const serverNames = availableServers.map(s => s.serverName);

    if (serverNames.includes(this.preferredServer)) {
      return this.preferredServer;
    }

    const preferredOrder = ['hd-1', 'hd-2', 'megacloud', 'vidstreaming', 'streamtape'];

    for (const preferred of preferredOrder) {
      if (serverNames.includes(preferred)) {
        return preferred;
      }
    }

    return serverNames[0];
  }

  applyServerToURL(serverName) {
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.set('server', serverName);
    return currentUrl.toString();
  }

  switchServer(serverName) {
    this.savePreferredServer(serverName);
    const newUrl = this.applyServerToURL(serverName);
    window.location.href = newUrl;
  }

  initializeServerButtons() {
    const buttons = document.querySelectorAll('.server-btn');

    buttons.forEach(button => {
      button.addEventListener('click', (e) => {
        e.preventDefault();
        const serverName = button.dataset.server;
        if (serverName) {
          this.switchServer(serverName);
        }
      });
    });
  }

  ensureCorrectServerOnLoad(currentServer, availableServers) {
    const params = new URLSearchParams(window.location.search);
    const urlServer = params.get('server');

    if (urlServer && this.isServerAvailable(urlServer, availableServers)) {
      this.savePreferredServer(urlServer);
      return;
    }

    const bestServer = this.selectBestServer(availableServers);

    if (!urlServer || urlServer !== bestServer) {
      const newUrl = this.applyServerToURL(bestServer);

      if (window.location.href !== newUrl) {
        window.location.href = newUrl;
      }
    }
  }
}

window.ServerManager = ServerManager;

document.addEventListener('DOMContentLoaded', () => {
  const serverManager = new ServerManager();
  serverManager.initializeServerButtons();
  window.serverManager = serverManager;
});

function switchServer(serverName) {
  if (window.serverManager) {
    window.serverManager.switchServer(serverName);
  } else {
    const currentUrl = new URL(window.location.href);
    currentUrl.searchParams.set('server', serverName);
    localStorage.setItem('yumePreferredServer', serverName);
    window.location.href = currentUrl.toString();
  }
}

window.switchServer = switchServer;
