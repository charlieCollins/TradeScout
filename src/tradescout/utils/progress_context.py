"""
Global Progress Context Manager

Provides a clean way to show progress for long-running operations without
polluting method signatures with callback parameters throughout the codebase.
"""

import threading
from typing import Optional, Callable
from contextlib import contextmanager


class ProgressContext:
    """Thread-local progress context for database operations"""
    
    def __init__(self):
        self._local = threading.local()
    
    def set_callback(self, callback: Optional[Callable[[str, int, int], None]]):
        """Set the progress callback for the current thread"""
        self._local.callback = callback
    
    def get_callback(self) -> Optional[Callable[[str, int, int], None]]:
        """Get the progress callback for the current thread"""
        return getattr(self._local, 'callback', None)
    
    def update(self, message: str, current: int, total: int):
        """Update progress if a callback is set"""
        callback = self.get_callback()
        if callback:
            callback(message, current, total)
    
    def clear(self):
        """Clear the progress callback"""
        self._local.callback = None


# Global instance
_progress_context = ProgressContext()


@contextmanager
def progress_context(callback: Callable[[str, int, int], None]):
    """
    Context manager for setting up progress tracking
    
    Usage:
        with progress_context(my_callback):
            # Any database operations in this block will show progress
            do_database_work()
    """
    _progress_context.set_callback(callback)
    try:
        yield
    finally:
        _progress_context.clear()


def update_progress(message: str, current: int, total: int):
    """Update progress if there's an active context"""
    _progress_context.update(message, current, total)


def has_progress_context() -> bool:
    """Check if there's an active progress context"""
    return _progress_context.get_callback() is not None