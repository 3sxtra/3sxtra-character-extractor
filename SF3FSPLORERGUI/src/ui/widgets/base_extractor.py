#!/usr/bin/env python3
"""
Base extractor widget for all extraction tools.
"""

import logging
import os
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from SF3FSPLORERGUI.src.utils.helpers import get_project_root


class BaseExtractorWidget(QWidget):
    """
    Base class for asset extraction widgets to reduce code duplication.
    """

    # pylint: disable=too-many-public-methods,unused-argument,unnecessary-pass

    worker_started = pyqtSignal()

    worker_finished = pyqtSignal()

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.worker = None

        # Common UI Elements
        self.title_label: QLabel | None = None
        self.progress_bar: QProgressBar | None = None
        self.status_label: QLabel | None = None
        self.action_btn: QPushButton | None = None
        self.cancel_btn: QPushButton | None = None

        # Common Extraction Elements
        self.source_path: QLineEdit | None = None
        self.output_path: QLineEdit | None = None
        self.file_list: QListWidget | None = None
        self.scanned_files: list[str] = []
        self.refresh_btn: QPushButton | None = None
        self.source_btn: QPushButton | None = None
        self.output_btn: QPushButton | None = None

    def setup_base_ui(self, layout):
        """Set up common UI elements"""
        # Header
        self.title_label = QLabel(self.windowTitle() if self.windowTitle() else "Asset Extraction")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(self.title_label)

        # Progress Section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.status_label = QLabel("Ready")
        progress_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        layout.addWidget(progress_group)

    def init_ui(self):
        """Template method for UI initialization"""
        layout = QVBoxLayout(self)

        # 1. Base UI (Title, Progress)
        self.setup_base_ui(layout)

        # 2. Content (Subclass Hook)
        self.add_content(layout)

        # 3. Actions (Subclass Hook)
        self.add_action_buttons(layout)

        layout.addStretch()

        # 4. Setup Worker
        self.setup_worker()

        # 5. Initial Scan
        self.scan_directory()

    def setup_worker(self):
        """Initialize the background worker"""
        self.worker = self.create_worker()
        if not self.worker:
            return

        # Common signals
        if hasattr(self.worker, "error"):
            self.worker.error.connect(self.on_error)
        if hasattr(self.worker, "finished"):
            self.worker.finished.connect(self.on_finished)

        # Progress signals
        if hasattr(self.worker, "progress"):
            self.worker.progress.connect(self.on_progress)
        elif hasattr(self.worker, "extraction_progress"):
            self.worker.extraction_progress.connect(self.on_progress)

        # Status signals
        if hasattr(self.worker, "status") and self.status_label:
            self.worker.status.connect(self.status_label.setText)

        # Completion signals (Try specific ones first, then generic)
        self.connect_completion_signal()

    def create_worker(self):
        """Abstract method to create specific worker"""
        raise NotImplementedError("Subclasses must implement create_worker")

    def connect_completion_signal(self):
        """Hook to connect specific completion signal"""
        if self.worker is None:
            return
        if hasattr(self.worker, "extraction_complete"):
            self.worker.extraction_complete.connect(self.on_complete)
        elif hasattr(self.worker, "recomposition_complete"):
            self.worker.recomposition_complete.connect(self.on_complete)
        elif hasattr(self.worker, "render_complete"):
            self.worker.render_complete.connect(self.on_complete)

    def add_content(self, layout):
        """Hook for adding main content. Default implementation creates a Config group."""
        config_group = QGroupBox("Configuration")
        config_layout = QFormLayout(config_group)
        self.add_config_elements(config_layout)
        # Insert between Title (0) and Progress (originally 1, now pushed down)
        layout.insertWidget(1, config_group)

    def setup_standard_content(self, layout, default_source_dir=None, default_output_dir=None, list_title="Files"):
        """
        Setup standard extract content: Source -> File List -> Output.
        Returns (source_group, list_group, output_group)
        """
        # 1. Source Selection
        if not default_source_dir:
            default_source_dir = get_project_root()
            # If afsextracted exists in root, use it as default source
            afsextracted = os.path.join(default_source_dir, "afsextracted")
            if os.path.exists(afsextracted):
                default_source_dir = afsextracted

        source_group, self.source_path = self.create_path_group(
            "Source Directory", default_source_dir, self.browse_source
        )
        self.source_btn = source_group.findChild(QPushButton)
        layout.addWidget(source_group)

        # 2. File List
        list_group = QGroupBox(list_title)
        list_layout = QVBoxLayout(list_group)

        self.file_list = QListWidget()
        list_layout.addWidget(self.file_list)

        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.scan_directory)
        list_layout.addWidget(self.refresh_btn)

        layout.addWidget(list_group)

        # 3. Output Directory
        if not default_output_dir:
            default_output_dir = os.path.join(get_project_root(), "output")

        output_group, self.output_path = self.create_path_group(
            "Output Directory", default_output_dir, self.browse_output
        )
        self.output_btn = output_group.findChild(QPushButton)
        layout.addWidget(output_group)

        return source_group, list_group, output_group

    def add_config_elements(self, layout):
        """Hook for subclasses to add configuration widgets to default config group"""
        pass

    def add_action_buttons(self, layout):
        """Hook for subclasses to add action buttons"""
        self.setup_action_buttons(layout, "Process", self.start_work)

    def start_work(self):
        """Default start work slot"""
        pass

    def create_path_widget(self, default_path, browse_callback):
        """Create a standard path selection widget (edit + btn)"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        path_edit = QLineEdit()
        path_edit.setText(default_path)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(browse_callback)

        layout.addWidget(path_edit)
        layout.addWidget(browse_btn)

        return widget, path_edit

    def create_path_group(self, title, default_path, browse_callback):
        """Create a standard path selection group"""
        group = QGroupBox(title)
        # Changed to QVBoxLayout to host the widget properly or keep generic
        layout = QVBoxLayout(group)

        widget, path_edit = self.create_path_widget(default_path, browse_callback)
        layout.addWidget(widget)

        return group, path_edit

    def browse_source(self):
        """Standard browse for source directory"""
        if self.source_path and self.browse_directory("Select Source Directory", self.source_path):
            self.scan_directory()

    def browse_output(self):
        """Standard browse for output directory"""
        if self.output_path:
            self.browse_directory("Select Output Directory", self.output_path)

    def browse_directory(self, title, path_edit):
        """Generic directory browser"""
        if not path_edit:
            return False
        directory = QFileDialog.getExistingDirectory(self, title, path_edit.text())
        if directory:
            path_edit.setText(directory)
            return True
        return False

    def scan_directory(self):
        """Template method for directory scanning"""
        pass

    def setup_action_buttons(self, layout, action_text="Process", action_callback=None):
        """Create and layout action buttons"""
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.action_btn = QPushButton(action_text)
        self.action_btn.setMinimumWidth(120)
        self.action_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 5px;")
        if action_callback:
            self.action_btn.clicked.connect(action_callback)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)

        action_layout.addWidget(self.cancel_btn)
        action_layout.addWidget(self.action_btn)

        layout.addLayout(action_layout)

    def cancel_processing(self):
        """Cancel the current operation"""
        if self.worker and self.worker.isRunning():
            if hasattr(self.worker, "stop"):
                self.worker.stop()
            if self.status_label:
                self.status_label.setText("Cancelling...")
            if self.cancel_btn:
                self.cancel_btn.setEnabled(False)

    def on_finished(self):
        """Handle worker finished"""
        self.reset_ui_state()
        self.worker_finished.emit()

    def start_ui_state(self):
        """Update UI state when starting worker"""
        if self.action_btn:
            self.action_btn.setEnabled(False)
        if self.cancel_btn:
            self.cancel_btn.setEnabled(True)
        if self.progress_bar:
            self.progress_bar.setValue(0)
            # Default to Indeterminate for start
            self.progress_bar.setRange(0, 0)
        if self.status_label:
            self.status_label.setText("Starting...")

    def run_worker_started(self):
        """Common logic for starting a worker after parameter setup"""
        self.start_ui_state()
        if self.worker:
            self.worker.start()
        self.worker_started.emit()

    def reset_ui_state(self):
        """Reset UI to default state"""
        if self.action_btn:
            self.action_btn.setEnabled(True)
        if self.cancel_btn:
            self.cancel_btn.setEnabled(False)
        if self.status_label:
            self.status_label.setText("Ready")
        if self.progress_bar:
            self.progress_bar.setValue(0)
            self.progress_bar.setRange(0, 100)

    def on_progress(self, current, total, message=None):
        """Handle progress updates"""
        if self.progress_bar:
            if total > 0:
                self.progress_bar.setValue(int((current / total) * 100))
            else:
                self.progress_bar.setRange(0, 0)  # Indeterminate

        if message and self.status_label:
            self.status_label.setText(message)

    def on_error(self, error_msg):
        """Handle errors"""
        QMessageBox.critical(self, "Error", f"Processing failed: {error_msg}")
        self.reset_ui_state()

    def on_complete(self, *args: Any) -> None:
        """Handle completion"""
        message = str(args[0]) if args else "Processing completed successfully"
        QMessageBox.information(self, "Success", message)
        if self.progress_bar:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
        if self.status_label:
            self.status_label.setText("Completed")

    def get_validated_output_dir(self) -> str | None:
        """Standard validation check for output directory and basic parameters"""
        if not (
            hasattr(self, "output_path")
            and self.output_path
            and hasattr(self, "source_path")
            and self.source_path
            and hasattr(self, "file_list")
            and self.file_list
        ):
            return None

        output_dir = self.output_path.text()
        if not self.validate_output_dir(output_dir):
            return None

        return output_dir

    def validate_output_dir(self, output_dir):
        """Validate output directory selection"""
        if not output_dir:
            QMessageBox.warning(self, "Warning", "Please select an output directory.")
            return False
        return True

    def validate_file_path(self, file_path, name="file"):
        """Validate a file path exists"""
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Warning", f"Please select a valid {name}.")
            return False
        return True

    def validate_selection(self, items, message="Please select a file to extract."):
        """Validate list selection"""
        if not items:
            QMessageBox.warning(self, "Warning", message)
            return False
        return True

    def scan_for_files(self, directory, extensions):
        """Standard file scanner for assets"""
        files: list[str] = []
        if not directory:
            self.logger.warning("Scan directory is empty/None")
            return files
        if not os.path.exists(directory):
            self.logger.warning("Scan directory does not exist: %s", directory)
            return files

        self.logger.info("Scanning directory: %s for extensions: %s", directory, extensions)
        try:
            for f in os.listdir(directory):
                if any(f.lower().endswith(ext.lower()) for ext in extensions):
                    files.append(os.path.join(directory, f))
            self.logger.info("Found %s files matching extensions", len(files))
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Error scanning directory %s: %s", directory, e)

        return files

    def get_game_root(self, source_dir: str) -> str:
        """
        Get game root directory from source directory.
        Assumes source_dir is likely 'afsextracted' inside the game root.
        """
        if not source_dir:
            return ""

        # Check if we are in afsextracted
        if os.path.basename(source_dir).lower() == "afsextracted":
            return os.path.dirname(source_dir)

        # Fallback: return source_dir itself
        return source_dir
