// class PersistentSyncNotification {
//     constructor() {
//         this.notification = null;
//         this.pollInterval = null;
//         this.isPolling = false;
//         this.lastStatus = null;
        
//         this.init();
//     }
    
//     init() {
//         // Start checking for sync progress on page load
//         this.startPolling();
        
//         // Listen for page visibility changes
//         document.addEventListener('visibilitychange', () => {
//             if (document.visibilityState === 'visible') {
//                 this.startPolling();
//             } else {
//                 this.stopPolling();
//             }
//         });
        
//         // Listen for beforeunload to stop polling
//         window.addEventListener('beforeunload', () => {
//             this.stopPolling();
//         });
//     }
    
//     async startPolling() {
//         if (this.isPolling) return;
        
//         this.isPolling = true;
//         this.pollInterval = setInterval(async () => {
//             await this.checkSyncProgress();
//         }, 2000); // Check every 2 seconds
        
//         // Initial check
//         await this.checkSyncProgress();
//     }
    
//     stopPolling() {
//         if (this.pollInterval) {
//             clearInterval(this.pollInterval);
//             this.pollInterval = null;
//         }
//         this.isPolling = false;
//     }
    

    
//     showSyncProgress(data) {
//         const isAutoSync = data.auto_sync || data.status === 'auto_syncing';
//         const percentage = Math.min(100, Math.max(0, data.percentage || 0));
        
//         if (!this.notification) {
//             this.createNotification();
//         }
        
//         const title = isAutoSync ? 'Auto-syncing AniList' : 'Syncing AniList';
//         const message = data.message || 'Syncing your watchlist...';
        
//         this.notification.innerHTML = `
//             <div class="flex items-center gap-4">
//                 <div class="flex-shrink-0">
//                     <div class="w-8 h-8 relative">
//                         <svg class="w-8 h-8 animate-spin text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                             <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
//                         </svg>
//                     </div>
//                 </div>
//                 <div class="flex-1 min-w-0">
//                     <div class="flex items-center justify-between mb-1">
//                         <p class="font-semibold text-white">${title}</p>
//                         <span class="text-sm text-blue-300 font-medium">${percentage.toFixed(0)}%</span>
//                     </div>
//                     <p class="text-sm text-blue-200 truncate">${message}</p>
//                     <div class="mt-2 w-full bg-blue-900/30 rounded-full h-2 overflow-hidden">
//                         <div class="h-full bg-gradient-to-r from-blue-500 to-blue-400 transition-all duration-500 ease-out" style="width: ${percentage}%"></div>
//                     </div>
//                 </div>
//                 ${!isAutoSync ? `
//                 <button onclick="window.persistentSyncNotification.hideNotification()" class="flex-shrink-0 p-1 hover:bg-white/10 rounded-lg transition-colors">
//                     <svg class="w-4 h-4 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                         <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
//                     </svg>
//                 </button>
//                 ` : ''}
//             </div>
//         `;
        
//         this.notification.className = 'persistent-sync-notification syncing';
//         this.showNotification();
//     }
    
//     showSyncCompleted(data) {
//         const isAutoSync = data.auto_sync || data.status === 'auto_sync_completed';
//         const synced = data.synced || 0;
//         const skipped = data.skipped || 0;
//         const failed = data.failed || 0;
//         const total = data.total || 0;
        
//         if (!this.notification) {
//             this.createNotification();
//         }
        
//         const title = isAutoSync ? 'Auto-sync Complete' : 'Sync Complete';
//         const message = `Added ${synced} new entries, skipped ${skipped} duplicates${failed > 0 ? `, ${failed} failed` : ''}`;
        
//         this.notification.innerHTML = `
//             <div class="flex items-center gap-4">
//                 <div class="flex-shrink-0">
//                     <div class="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
//                         <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                             <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
//                         </svg>
//                     </div>
//                 </div>
//                 <div class="flex-1 min-w-0">
//                     <p class="font-semibold text-white">${title}</p>
//                     <p class="text-sm text-green-200">${message}</p>
//                 </div>
//                 <button onclick="window.persistentSyncNotification.hideNotification()" class="flex-shrink-0 p-1 hover:bg-white/10 rounded-lg transition-colors">
//                     <svg class="w-4 h-4 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                         <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
//                     </svg>
//                 </button>
//             </div>
//         `;
        
//         this.notification.className = 'persistent-sync-notification completed';
//         this.showNotification();
//     }
    
//     showSyncError(data) {
//         const isAutoSync = data.auto_sync || data.status === 'auto_sync_error';
//         const error = data.error || data.message || 'Unknown error';
        
//         if (!this.notification) {
//             this.createNotification();
//         }
        
//         const title = isAutoSync ? 'Auto-sync Failed' : 'Sync Failed';
        
//         this.notification.innerHTML = `
//             <div class="flex items-center gap-4">
//                 <div class="flex-shrink-0">
//                     <div class="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
//                         <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                             <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
//                         </svg>
//                     </div>
//                 </div>
//                 <div class="flex-1 min-w-0">
//                     <p class="font-semibold text-white">${title}</p>
//                     <p class="text-sm text-red-200 truncate">${error}</p>
//                 </div>
//                 <button onclick="window.persistentSyncNotification.hideNotification()" class="flex-shrink-0 p-1 hover:bg-white/10 rounded-lg transition-colors">
//                     <svg class="w-4 h-4 text-white/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
//                         <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
//                     </svg>
//                 </button>
//             </div>
//         `;
        
//         this.notification.className = 'persistent-sync-notification error';
//         this.showNotification();
//     }
    
//     createNotification() {
//         this.notification = document.createElement('div');
//         this.notification.id = 'persistent-sync-notification';
//         this.notification.style.cssText = `
//             position: fixed;
//             top: 20px;
//             right: 20px;
//             z-index: 9999;
//             max-width: 400px;
//             padding: 16px;
//             border-radius: 12px;
//             box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
//             backdrop-filter: blur(10px);
//             border: 1px solid rgba(255, 255, 255, 0.1);
//             transform: translateX(100%);
//             transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
//             opacity: 0;
//         `;
        
//         document.body.appendChild(this.notification);
//     }
    
//     showNotification() {
//         if (!this.notification) return;
        
//         // Update colors based on status
//         if (this.notification.classList.contains('syncing')) {
//             this.notification.style.background = 'linear-gradient(135deg, rgba(59, 130, 246, 0.9), rgba(37, 99, 235, 0.9))';
//         } else if (this.notification.classList.contains('completed')) {
//             this.notification.style.background = 'linear-gradient(135deg, rgba(34, 197, 94, 0.9), rgba(21, 128, 61, 0.9))';
//         } else if (this.notification.classList.contains('error')) {
//             this.notification.style.background = 'linear-gradient(135deg, rgba(239, 68, 68, 0.9), rgba(220, 38, 38, 0.9))';
//         }
        
//         // Animate in
//         setTimeout(() => {
//             this.notification.style.transform = 'translateX(0)';
//             this.notification.style.opacity = '1';
//         }, 100);
//     }
    
//     hideNotification() {
//         if (!this.notification) return;
        
//         this.notification.style.transform = 'translateX(100%)';
//         this.notification.style.opacity = '0';
        
//         setTimeout(() => {
//             if (this.notification && this.notification.parentNode) {
//                 this.notification.remove();
//                 this.notification = null;
//             }
//         }, 300);
//     }
// }

// // Initialize persistent sync notification system
// document.addEventListener('DOMContentLoaded', function() {
//     window.persistentSyncNotification = new PersistentSyncNotification();
// });
