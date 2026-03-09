class ServerManager {
  constructor() {
    this.storageKey = 'yumePreferredServer';
    this.preferredServer = this.loadPreferredServer();
  }

  loadPreferredServer() {
    try {
      return localStorage.getItem(this.storageKey) || 'kiwi';
    } catch (error) {
      console.error('Error loading preferred server:', error);
      return 'kiwi';
    }
  }

  savePreferredServer(serverName) {
    try {
      localStorage.setItem(this.storageKey, serverName);
      document.cookie = `preferred_server=${serverName}; path=/; max-age=31536000`;
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
      return 'kiwi';
    }

    const serverNames = availableServers.map(s => s.serverName);

    if (serverNames.includes(this.preferredServer)) {
      return this.preferredServer;
    }

    const preferredOrder = ['kiwi', 'arc', 'zoro', 'bee', 'jet', 'wco'];

    for (const preferred of preferredOrder) {
      if (serverNames.includes(preferred)) {
        return preferred;
      }
    }

    return serverNames[0];
  }

  switchServer(serverName) {
    this.savePreferredServer(serverName);
    // Use AJAX-based switching if available (watch page), otherwise reload
    if (typeof window.switchProvider === 'function') {
      window.switchProvider(serverName);
    } else {
      window.location.reload();
    }
  }

  initializeServerButtons() {
    // Provider dropdown on the watch page
    const providerDropdown = document.getElementById('providerDropdown');
    if (providerDropdown) {
      // Set dropdown to match stored preference on load
      for (const opt of providerDropdown.options) {
        if (opt.value === this.preferredServer) {
          opt.selected = true;
          break;
        }
      }
    }
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
    if (typeof window.switchProvider === 'function') {
      window.switchProvider(serverName);
    } else {
      window.location.reload();
    }
  }
}

window.switchServer = switchServer;
