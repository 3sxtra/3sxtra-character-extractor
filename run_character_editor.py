import os
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from SF3FSPLORERGUI.src.ui.character_editor.window import CharacterExtractorWindow

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    app = QApplication(sys.argv)

    # Initialize logging
    from sf33rd.core.logger import setup_logging

    setup_logging()

    # Apply dark theme (same as main GUI)
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QPalette

    palette = QPalette()
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
    app.setPalette(palette)

    # Stylesheet for specific controls
    app.setStyleSheet("""
        QToolTip { color: #ffffff; background-color: #2a2a2a; border: 1px solid white; }
        QMenuBar { background-color: #2d2d2d; color: #ffffff; }
        QMenuBar::item:selected { background-color: #3d3d3d; }
        QMenu { background-color: #2d2d2d; color: #ffffff; border: 1px solid #3d3d3d; }
        QMenu::item:selected { background-color: #3d3d3d; }
        QTabBar::tab { background-color: #2d2d2d; color: #ffffff; padding: 8px 12px;
                       border-top-left-radius: 4px; border-top-right-radius: 4px; }
        QTabBar::tab:selected { background-color: #3d3d3d; border-bottom: 2px solid #2a82da; }
        QHeaderView::section { background-color: #2d2d2d; color: #ffffff; padding: 4px;
                               border: 1px solid #3d3d3d; }
        QScrollBar:vertical { border: none; background: #2d2d2d; width: 12px; margin: 0px; }
        QScrollBar::handle:vertical { background: #888888; min-height: 20px; border-radius: 6px; margin: 2px; }
        QScrollBar::handle:vertical:hover { background: #aaaaaa; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        QScrollBar:horizontal { border: none; background: #2d2d2d; height: 12px; margin: 0px; }
        QScrollBar::handle:horizontal { background: #888888; min-width: 20px; border-radius: 6px; margin: 2px; }
        QScrollBar::handle:horizontal:hover { background: #aaaaaa; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
    """)

    # Set app icon - check resources folder first, then fallback to root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "SF3FSPLORERGUI", "resources", "icons", "app_icon.png")
    if not os.path.exists(icon_path):
        # Fallback to root for backwards compatibility
        icon_path = os.path.join(script_dir, "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Launch Character Extractor directly
    window = CharacterExtractorWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
