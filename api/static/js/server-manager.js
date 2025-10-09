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

      fetch('/api/set-server', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ server: serverName })
      }).catch(err => console.error('Failed to sync server to backend:', err));
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
    window.location.reload();
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
    const bestServer = this.selectBestServer(availableServers);

    if (currentServer !== bestServer) {
      this.savePreferredServer(bestServer);
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
    localStorage.setItem('yumePreferredServer', serverName);
    window.location.reload();
  }
}

window.switchServer = switchServer;
