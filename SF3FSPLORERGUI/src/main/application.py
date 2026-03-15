#!/usr/bin/env python3
"""
Main application entry point and lifecycle management
"""

import argparse
import logging
import signal
import sys
import traceback
from typing import cast

from PyQt6.QtCore import QCoreApplication, Qt, QTimer
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QMessageBox

# Import global constants
from SF3FSPLORERGUI.src.main import APP_NAME, APP_VERSION, COMPANY_NAME
from SF3FSPLORERGUI.src.main.monkey_patch import apply_monkey_patches, get_patcher, setup_gui_callbacks
from SF3FSPLORERGUI.src.ui.main_window import MainWindow
from SF3FSPLORERGUI.src.utils.config import Configuration
from SF3FSPLORERGUI.src.utils.logger import setup_logging


class SF3AssetExplorer:
    """Main application class for SF3:3rd Asset Explorer"""

    def __init__(self, args=None):
        """
        Initialize the application

        Args:
            args: Command line arguments
        """
        self.args = args or []
        self.config = None
        self.main_window = None
        # Initialize self.logger to a basic default to avoid NoneType errors
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # Application state
        self.is_running = False
        self.workers = []
        self.gui_handler = None

    def setup_logging(self):
        """Set up logging configuration"""
        try:
            config = self.config or {}
            log_level = getattr(logging, config.get("logging.level", "INFO"))
            log_file = config.get("logging.file_enabled") and config.get("logging.file_path")

            # Use the enhanced logging setup
            logging_result = setup_logging(level=log_level, log_file=log_file, console_output=True, enable_colors=True)

            self.logger = logging_result["logger"]
            self.gui_handler = logging_result["gui_handler"]

            self.logger.info("Starting %s v%s", APP_NAME, APP_VERSION)
            self.logger.info("Logging level: %s", logging.getLevelName(log_level))
            if log_file:
                self.logger.info("Log file: %s", log_file)

        except (OSError, ImportError, ValueError) as e:
            # Fallback to basic logging
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.logger.error("Failed to setup logging: %s", e)

    def load_configuration(self):
        """Load application configuration"""
        try:
            config_path = self.args.config if hasattr(self.args, "config") else None
            self.config = Configuration(config_path)
            self.config.load_config()
            self.logger.info("Configuration loaded successfully")
        except (OSError, ValueError) as e:
            self.logger.error("Failed to load configuration: %s", e)
            QMessageBox.critical(None, "Configuration Error", f"Failed to load configuration: {e}")
            sys.exit(1)

    def setup_dark_theme(self):
        """Apply a modern dark theme to the application"""
        # Create a dark palette
        palette = QPalette()

        # Base colors
        dark_color = QColor(45, 45, 45)
        text_color = QColor(255, 255, 255)

        palette.setColor(QPalette.ColorRole.Window, dark_color)
        palette.setColor(QPalette.ColorRole.WindowText, text_color)
        palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.ColorRole.AlternateBase, dark_color)
        palette.setColor(QPalette.ColorRole.ToolTipBase, text_color)
        palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
        palette.setColor(QPalette.ColorRole.Text, text_color)
        palette.setColor(QPalette.ColorRole.Button, dark_color)
        palette.setColor(QPalette.ColorRole.ButtonText, text_color)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

        # Apply palette
        app = cast(QApplication, QApplication.instance())
        if app:
            app.setPalette(palette)

        # Set stylesheet for specific controls to ensure consistent look
        app = cast(QApplication, QApplication.instance())
        if app:
            app.setStyleSheet("""
            QToolTip {
                color: #ffffff;
                background-color: #2a2a2a;
                border: 1px solid white;
            }
            QMenuBar {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            QMenuBar::item:selected {
                background-color: #3d3d3d;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
            }
            QMenu::item:selected {
                background-color: #3d3d3d;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #3d3d3d;
                border-bottom: 2px solid #2a82da;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 4px;
                border: 1px solid #3d3d3d;
            }
            QScrollBar:vertical {
                border: none;
                background: #2d2d2d;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #888888;
                min-height: 20px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #aaaaaa;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #2d2d2d;
                height: 12px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #888888;
                min-width: 20px;
                border-radius: 6px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #aaaaaa;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

    def initialize_services(self):
        """Initialize application services"""
        try:
            # Apply monkey patches for sf33rd integration
            apply_monkey_patches()
            self.logger.info("Services initialized successfully")
        except Exception as e:
            self.logger.error("Failed to initialize services: %s", e)
            raise

    def create_main_window(self):
        """Create and setup the main window"""
        try:
            self.main_window = MainWindow(self)
            self.main_window.showMaximized()
            self.logger.info("Main window created successfully")
        except Exception as e:
            self.logger.error("Failed to create main window: %s", e)
            raise

    def setup_signal_connections(self):
        """Setup signal/slot connections"""
        try:
            # Connect application signals
            if self.main_window and hasattr(self.main_window, "console_widget"):
                # Setup GUI callbacks for monkey patch system
                setup_gui_callbacks(
                    output_callback=self.main_window.console_widget.append_text,
                    error_callback=lambda msg: self.main_window.console_widget.append_text(msg, "ERROR"),
                    log_callback=self.main_window.console_widget.append_log_message,
                )
                self.logger.info("GUI callbacks connected successfully")

            # Connect application quit signal
            app = cast(QApplication, QApplication.instance())
            if app:
                app.aboutToQuit.connect(self.on_about_to_quit)

            # Setup signal handlers for graceful shutdown
            self.setup_signal_handlers()

            self.logger.info("Signal connections setup completed")
        except Exception as e:
            self.logger.error("Failed to setup signal connections: %s", e)
            raise

    def run(self):
        """Run the application"""
        try:
            self.is_running = True
            self.logger.info("Application started successfully")

            # Start the Qt event loop
            exit_code = QApplication.exec()
            return exit_code

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Application error: %s", e)
            QMessageBox.critical(self.main_window, "Application Error", str(e))
            return 1

    def cleanup(self):
        """Clean up application resources"""
        try:
            self.is_running = False
            self.logger.info("Starting application cleanup...")

            # Stop all workers gracefully
            self.logger.debug("Stopping %s workers...", len(self.workers))
            for worker in self.workers:
                try:
                    if hasattr(worker, "cancel"):
                        worker.cancel()
                    elif hasattr(worker, "stop"):
                        worker.stop()
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.warning("Error stopping worker %s: %s", worker, e)

            # Wait for workers to finish with timeout
            for worker in self.workers:
                try:
                    if hasattr(worker, "thread") and worker.thread().isRunning():
                        worker.thread().quit()
                        if not worker.thread().wait(3000):  # 3 second timeout
                            self.logger.warning("Worker %s did not terminate gracefully", worker)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.warning("Error waiting for worker %s: %s", worker, e)

            # Clean up main window
            if self.main_window:
                try:
                    self.main_window.save_window_state()
                    self.logger.debug("Main window state saved")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self.logger.warning("Error saving window state: %s", e)

            # Save configuration
            if self.config:
                try:
                    self.config.save_config()
                    self.logger.info("Configuration saved")
                except (OSError, ValueError) as e:
                    self.logger.error("Failed to save configuration: %s", e)

            # Clean up monkey patches
            try:
                patcher = get_patcher()
                patcher.remove_monkey_patches()
                self.logger.debug("Monkey patches removed")
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.logger.warning("Error removing monkey patches: %s", e)

            self.logger.info("Application cleanup completed")

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Error during cleanup: %s", e)
            self.logger.debug("Cleanup error details: %s", traceback.format_exc())

    def quit(self):
        """Quit the application"""
        self.logger.info("Application quit requested")
        self.cleanup()
        QCoreApplication.quit()

    def on_about_to_quit(self):
        """Handle application about to quit signal"""
        self.logger.info("Application is about to quit")
        # Additional cleanup can be done here if needed

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        try:
            # Handle SIGINT (Ctrl+C)
            signal.signal(signal.SIGINT, self._signal_handler)
            # Handle SIGTERM
            signal.signal(signal.SIGTERM, self._signal_handler)

            # Create a timer to handle Python signal handling in Qt event loop
            timer = QTimer()
            timer.start(500)  # 500ms
            timer.timeout.connect(lambda: None)  # Keep the timer active

            self.logger.debug("Signal handlers setup completed")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.warning("Could not setup signal handlers: %s", e)

    def _signal_handler(self, signum, _frame):
        """Handle system signals"""
        signal_name = {signal.SIGINT: "SIGINT", signal.SIGTERM: "SIGTERM"}.get(signum, f"SIGNAL {signum}")
        self.logger.info("Received %s, shutting down gracefully...", signal_name)
        self.quit()


def main():
    """Application entry point"""
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(COMPANY_NAME)

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="SF3:3rd Asset Explorer")
    parser.add_argument("--config", type=str, help="Configuration file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    try:
        # Create and initialize application
        sf3_app = SF3AssetExplorer(args)
        sf3_app.load_configuration()
        sf3_app.setup_logging()
        sf3_app.setup_dark_theme()
        sf3_app.initialize_services()
        sf3_app.create_main_window()
        sf3_app.setup_signal_connections()

        # Run application
        exit_code = sf3_app.run()
        return exit_code

    except KeyboardInterrupt:
        print("Application interrupted by user", file=sys.stderr)
        return 1
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Fatal error: {e}", file=sys.stderr)
        print(f"Traceback: {traceback.format_exc()}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
