#!/usr/bin/env python3
"""
About dialog with application information
"""

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class BaseAboutDialog(QDialog):
    """Base about dialog with shared structure - subclass to customize content."""

    # Override these in subclasses
    WINDOW_TITLE = "About"
    APP_NAME = "Application"
    APP_VERSION = "Version 0.0.1"
    APP_AUTHOR = "Daouid / SF33RD Community"
    APP_DESCRIPTION = "Application description."
    FEATURES: list[str] = []
    MAIN_DEPENDENCIES: dict[str, str] = {}
    DEV_DEPENDENCIES = {
        "pytest": "7.0+ - Testing framework",
        "pytest-qt": "4.0+ - Qt testing support",
        "black": "Code formatting",
        "flake8": "Code linting",
        "mypy": "Type checking",
    }

    def __init__(self, parent=None):
        """Initialize the about dialog."""
        super().__init__(parent)

        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        # Initialize attributes
        self.tab_widget = None
        self.about_tab = None
        self.dependencies_tab = None
        self.license_tab = None
        self.ok_button = None

        self.setup_ui()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Create tabs
        self.create_about_tab()
        self.create_dependencies_tab()
        self.create_license_tab()

        # Add tabs to widget
        self.tab_widget.addTab(self.about_tab, "About")
        self.tab_widget.addTab(self.dependencies_tab, "Dependencies")
        self.tab_widget.addTab(self.license_tab, "License")

        # Add tab widget to layout
        layout.addWidget(self.tab_widget)

        # Create buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        # Add OK button
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        buttons_layout.addWidget(self.ok_button)

        layout.addLayout(buttons_layout)

    def create_about_tab(self):
        """Create the about tab."""
        self.about_tab = QWidget()
        layout = QVBoxLayout(self.about_tab)

        # Application info group
        info_group = QGroupBox("Application Information")
        info_layout = QFormLayout()

        # Application name and version
        name_label = QLabel(self.APP_NAME)
        name_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        info_layout.addRow("Name:", name_label)

        version_label = QLabel(self.APP_VERSION)
        info_layout.addRow("Version:", version_label)

        # Author information
        author_label = QLabel(self.APP_AUTHOR)
        info_layout.addRow("Author:", author_label)

        # Description
        description_text = QTextEdit()
        description_text.setPlainText(self.APP_DESCRIPTION)
        description_text.setReadOnly(True)
        description_text.setMaximumHeight(70)
        description_text.setStyleSheet("border: none; background-color: transparent;")
        info_layout.addRow("Description:", description_text)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Features group
        features_group = QGroupBox("Features")
        features_layout = QVBoxLayout()

        for feature in self.FEATURES:
            feature_label = QLabel(feature)
            feature_label.setWordWrap(True)
            features_layout.addWidget(feature_label)

        features_group.setLayout(features_layout)
        layout.addWidget(features_group)

        layout.addStretch()

    def create_dependencies_tab(self):
        """Create the dependencies tab."""
        self.dependencies_tab = QWidget()
        layout = QVBoxLayout(self.dependencies_tab)

        # Main dependencies group
        main_group = QGroupBox("Main Dependencies")
        main_layout = QFormLayout()

        for dep, description in self.MAIN_DEPENDENCIES.items():
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            main_layout.addRow(dep, desc_label)

        main_group.setLayout(main_layout)
        layout.addWidget(main_group)

        # Development dependencies group
        dev_group = QGroupBox("Development Dependencies")
        dev_layout = QFormLayout()

        for dep, description in self.DEV_DEPENDENCIES.items():
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            dev_layout.addRow(dep, desc_label)

        dev_group.setLayout(dev_layout)
        layout.addWidget(dev_group)

        layout.addStretch()

    def create_license_tab(self):
        """Create the license tab."""
        self.license_tab = QWidget()
        layout = QVBoxLayout(self.license_tab)

        license_info = QTextEdit()
        license_text = (
            "MIT License\n\n"
            "Copyright (c) 2025-2026 Daouid / SF33RD Community\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy "
            'of this software and associated documentation files (the "Software"), to deal '
            "in the Software without restriction, including without limitation the rights "
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
            "copies of the Software, and to permit persons to whom the Software is "
            "furnished to do so, subject to the following conditions:\n\n"
            "The above copyright notice and this permission notice shall be included in all "
            "copies or substantial portions of the Software.\n\n"
            'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR '
            "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
            "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
            "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
            "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, "
            "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE "
            "SOFTWARE."
        )
        license_info.setPlainText(license_text)
        license_info.setReadOnly(True)
        license_info.setStyleSheet("font-family: Consolas, Courier New, monospace;")
        layout.addWidget(license_info)


class AboutDialog(BaseAboutDialog):
    """About dialog for SF3:3rd Asset Explorer."""

    WINDOW_TITLE = "About SF3:3rd Asset Explorer"
    APP_NAME = "SF3:3rd Asset Explorer"
    APP_DESCRIPTION = (
        "A comprehensive toolkit for exploring, extracting, and editing assets "
        "from Street Fighter III: 3rd Strike (CPS3). Browse AFS archives, extract "
        "characters, stages, UI elements, and audio files."
    )
    FEATURES = [
        "File Browser - Navigate AFS archives and extracted directories",
        "Character Extractor - Extract sprites, frames, and animations",
        "Stage Extractor - Extract and recompose background layers",
        "UI Extractor - Extract menus, HUD elements, and graphics",
        "Audio Tools - Extract ADX music and BD sound effects",
        "Universal Preview - Preview images and play audio files",
        "Tools Menu - Launch dedicated Character and Stage Editors",
    ]
    MAIN_DEPENDENCIES = {
        "PyQt6": "6.5+ - GUI framework",
        "sf33rd": "External library for game asset processing",
        "mutagen": "Audio metadata extraction",
        "numpy": "Numerical computing",
        "pydub": "Audio format conversion",
        "pillow": "Image processing",
        "opencv-python": "Advanced image operations",
    }

    @staticmethod
    def show_about_dialog(parent=None):
        """Static method to show the about dialog."""
        dialog = AboutDialog(parent)
        dialog.exec()
