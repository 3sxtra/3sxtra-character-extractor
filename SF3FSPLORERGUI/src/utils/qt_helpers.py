"""
Qt specific helper classes and mixins.
"""

from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class DragDropFileHandlerMixin:
    """
    Mixin for handling file drag and drop events in Qt widgets.
    Requires the subclass to implement on_file_dropped(file_path).
    """

    def drag_enter_event(self, event: QDragEnterEvent | None) -> None:
        """Handle drag and drop enter event."""
        if not event:
            return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            event.acceptProposedAction()

    def drop_event(self, event: QDropEvent | None) -> None:
        """Handle file drop event."""
        if not event:
            return
        mime_data = event.mimeData()
        if mime_data and mime_data.hasUrls():
            for url in mime_data.urls():
                file_path = url.toLocalFile()
                if self.on_file_dropped(file_path):
                    break

    def on_file_dropped(self, file_path: str) -> bool:
        """
        Handle the dropped file.
        Override this method in the subclass.

        Args:
            file_path: Path to the dropped file.

        Returns:
            bool: True if file was handled and processing should stop, False otherwise.
        """
        raise NotImplementedError("Subclasses must implement on_file_dropped")
