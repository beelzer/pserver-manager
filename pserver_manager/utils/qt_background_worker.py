"""Generic Qt background worker for running tasks without blocking the UI.

This module provides reusable base classes for Qt threading to eliminate
code duplication across different worker implementations.
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from PySide6.QtCore import QObject, QThread, Signal

T = TypeVar('T')


class BackgroundWorker(QObject, Generic[T]):
    """Generic worker that runs tasks in a background thread.

    This base class handles all the Qt threading boilerplate, allowing
    subclasses to focus on the actual work to be done.
    """

    # Signals
    finished = Signal(object)  # Result of type T
    error = Signal(str)  # Error message

    def __init__(self, task_func: Callable[..., T], *args: Any, **kwargs: Any) -> None:
        """Initialize worker with a task function.

        Args:
            task_func: Function to execute in background thread
            *args: Positional arguments for task_func
            **kwargs: Keyword arguments for task_func
        """
        super().__init__()
        self._task_func = task_func
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def run(self) -> None:
        """Run the task in the background thread.

        This method is called when the thread starts. It executes the task
        function and emits the appropriate signal based on success or failure.
        """
        try:
            result = self._task_func(*self._args, **self._kwargs)
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def cancel(self) -> None:
        """Cancel the task execution.

        This sets a flag that prevents signals from being emitted.
        Note: This does not stop the task if it's already running.
        """
        self._cancelled = True


class BackgroundHelper(QObject, Generic[T]):
    """Generic helper for managing background tasks in Qt applications.

    This class handles thread lifecycle, worker management, and cleanup,
    providing a simple interface for running tasks in the background.

    Example usage:
        >>> helper = BackgroundHelper()
        >>> helper.finished.connect(self.on_result)
        >>> helper.error.connect(self.on_error)
        >>> helper.run_task(my_function, arg1, arg2)
    """

    # Expose signals at helper level
    finished = Signal(object)  # Result of type T
    error = Signal(str)

    def __init__(self) -> None:
        """Initialize helper."""
        super().__init__()
        self.thread: QThread | None = None
        self.worker: BackgroundWorker[T] | None = None

    def run_task(
        self, task_func: Callable[..., T], *args: Any, **kwargs: Any
    ) -> None:
        """Run a task in the background.

        Args:
            task_func: Function to execute in background thread
            *args: Positional arguments for task_func
            **kwargs: Keyword arguments for task_func
        """
        # Clean up previous thread if running
        if self.thread is not None:
            self.stop_task()

        # Create worker and thread
        self.worker = BackgroundWorker(task_func, *args, **kwargs)
        self.thread = QThread()

        # Move worker to thread
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.finished.emit)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self.error.emit)
        self.worker.error.connect(self._on_error)

        # Start thread
        self.thread.start()

    def stop_task(self) -> None:
        """Stop the current task and clean up resources."""
        if self.worker:
            self.worker.cancel()

        if self.thread:
            self.thread.quit()
            self.thread.wait(5000)  # Wait up to 5 seconds
            self.thread = None

        self.worker = None

    def _on_finished(self, result: T) -> None:
        """Handle task completion.

        Args:
            result: Result from the task
        """
        self.stop_task()

    def _on_error(self, error: str) -> None:
        """Handle task error.

        Args:
            error: Error message
        """
        self.stop_task()

    @property
    def is_running(self) -> bool:
        """Check if a task is currently running.

        Returns:
            True if a task is in progress, False otherwise
        """
        return self.thread is not None and self.thread.isRunning()
