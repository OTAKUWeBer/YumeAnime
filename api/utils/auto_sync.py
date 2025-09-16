"""
Auto-sync functionality for AniList watchlist
Handles background sync when user connects AniList account
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from .helpers import sync_anilist_watchlist_blocking, store_sync_progress, get_sync_progress
from ..models.user import get_user_by_id

logger = logging.getLogger(__name__)

# Global storage for auto-sync status
auto_sync_status = {}

class AutoSyncManager:
    def __init__(self):
        self.sync_tasks = {}
        self.last_sync_times = {}
        
    def should_auto_sync(self, user_id: int) -> bool:
        """Check if user should be auto-synced"""
        try:
            user = get_user_by_id(user_id)
            if not user or not user.get('anilist_access_token'):
                return False
            
            # Check if last sync was more than 24 hours ago
            last_sync = self.last_sync_times.get(user_id, 0)
            return (time.time() - last_sync) > (24 * 60 * 60)  # 24 hours
            
        except Exception as e:
            logger.error(f"Error checking auto-sync eligibility for user {user_id}: {e}")
            return False
    
    def start_auto_sync(self, user_id: int) -> bool:
        """Start auto-sync for a user"""
        try:
            if user_id in self.sync_tasks:
                logger.info(f"Auto-sync already running for user {user_id}")
                return False
            
            if not self.should_auto_sync(user_id):
                logger.info(f"Auto-sync not needed for user {user_id}")
                return False
            
            # Start background sync
            task = asyncio.create_task(self._run_auto_sync(user_id))
            self.sync_tasks[user_id] = task
            
            logger.info(f"Started auto-sync for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting auto-sync for user {user_id}: {e}")
            return False
    
    async def _run_auto_sync(self, user_id: int):
        """Run the actual auto-sync process"""
        try:
            user = get_user_by_id(user_id)
            if not user or not user.get('anilist_access_token'):
                return
            
            access_token = user['anilist_access_token']
            
            # Store initial progress
            store_sync_progress(user_id, {
                'status': 'auto_syncing',
                'processed': 0,
                'total': 0,
                'synced': 0,
                'skipped': 0,
                'failed': 0,
                'percentage': 0,
                'message': 'Auto-sync in progress...',
                'auto_sync': True
            })
            
            def progress_callback(progress):
                try:
                    store_sync_progress(user_id, {
                        'status': 'auto_syncing',
                        'processed': progress.processed,
                        'total': progress.total,
                        'synced': progress.synced,
                        'skipped': progress.skipped,
                        'failed': progress.failed,
                        'percentage': progress.percentage,
                        'estimated_remaining': getattr(progress, 'estimated_remaining', 0),
                        'message': f'Auto-syncing... {progress.processed}/{progress.total}',
                        'auto_sync': True
                    })
                except Exception as e:
                    logger.warning(f"Auto-sync progress callback error: {e}")
            
            # Run sync
            result = sync_anilist_watchlist_blocking(user_id, access_token, progress_callback)
            
            # Store final result
            if 'error' in result:
                store_sync_progress(user_id, {
                    'status': 'auto_sync_error',
                    'message': f'Auto-sync failed: {result["error"]}',
                    'error': result['error'],
                    'auto_sync': True
                })
            else:
                synced_count = result.get('synced_count', 0)
                skipped_count = result.get('skipped_count', 0)
                failed_count = result.get('failed_count', 0)
                total_count = result.get('total_count', 0)
                
                store_sync_progress(user_id, {
                    'status': 'auto_sync_completed',
                    'processed': total_count,
                    'total': total_count,
                    'synced': synced_count,
                    'skipped': skipped_count,
                    'failed': failed_count,
                    'percentage': 100,
                    'message': f'Auto-sync completed! {synced_count + skipped_count}/{total_count} entries processed.',
                    'auto_sync': True
                })
                
                # Update last sync time
                self.last_sync_times[user_id] = time.time()
            
            logger.info(f"Auto-sync completed for user {user_id}")
            
        except Exception as e:
            logger.error(f"Auto-sync error for user {user_id}: {e}")
            store_sync_progress(user_id, {
                'status': 'auto_sync_error',
                'message': f'Auto-sync failed: {str(e)}',
                'error': str(e),
                'auto_sync': True
            })
        finally:
            # Clean up task reference
            self.sync_tasks.pop(user_id, None)

# Global auto-sync manager instance
auto_sync_manager = AutoSyncManager()

def trigger_auto_sync(user_id: int) -> bool:
    """Trigger auto-sync for a user (called when AniList is connected)"""
    return auto_sync_manager.start_auto_sync(user_id)

def get_auto_sync_status(user_id: int) -> Dict[str, Any]:
    """Get auto-sync status for a user"""
    is_running = user_id in auto_sync_manager.sync_tasks
    last_sync = auto_sync_manager.last_sync_times.get(user_id, 0)
    
    return {
        'is_running': is_running,
        'last_sync': last_sync,
        'last_sync_formatted': datetime.fromtimestamp(last_sync).strftime('%Y-%m-%d %H:%M:%S') if last_sync else None,
        'should_sync': auto_sync_manager.should_auto_sync(user_id)
    }