# SF3:3rd Strike Character Extractor

A tool for viewing and extracting character sprites from *Street Fighter III: 3rd Strike* (PS2 version).

## Features

*   **Character Extractor GUI**: Visual editor for viewing character sprites, animations, and palettes.
*   **Asset Extraction**: Extract character sprites with proper palettes applied.
*   **Direct AFS Archive Support**: Read directly from `SF33RD.AFS` without requiring extraction.
*   **Palette Handling**: Automatically handle and apply the correct color palettes for sprites.
*   **Frame Recomposition**: Reconstruct animation frames from raw sprite data.

## System Requirements

*   **Operating System**: Windows, macOS, or Linux
*   **Python Version**: 3.10+ (3.12 recommended)
*   **Package Manager**: [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### Using uv (Recommended)

[uv](https://docs.astral.sh/uv/) is a fast Python package manager that handles dependencies automatically.

1.  Install uv (if not already installed):

    **Windows (PowerShell)**:
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

    **macOS/Linux**:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  Extract the zip file to a folder of your choice.

3.  Run the Character Extractor - dependencies are installed automatically:

    **Windows**:
    ```bash
    run.bat
    ```

    **macOS/Linux**:
    ```bash
    chmod +x run.sh
    ./run.sh
    ```

### Using pip (Alternative)

1.  Extract the zip file to a folder of your choice.

2.  Install dependencies:

    ```bash
    pip install .
    ```

3.  Run the tool:

    ```bash
    python run_character_editor.py
    ```

## Usage

### Character Extractor (GUI)

The easiest way to explore characters is through the graphical editor:

```bash
uv run run_character_editor.py
```

Or use the launcher script:

**Windows**: `run.bat`

**macOS/Linux**: `./run.sh`

### AFS Data Source

The tool automatically searches for game assets in this priority order:

**Windows**:
1. `%APPDATA%\CrowdedStreet\3SX\resources\SF33RD.AFS` (archive)
2. `{cwd}\SF33RD.AFS` (archive)
3. `%APPDATA%\CrowdedStreet\3SX\resources\afsextracted\` (folder)
4. `{cwd}\afsextracted\` (folder)

**macOS**:
1. `~/Library/Application Support/CrowdedStreet/3SX/resources/SF33RD.AFS` (archive)
2. `{cwd}/SF33RD.AFS` (archive)
3. `~/Library/Application Support/CrowdedStreet/3SX/resources/afsextracted/` (folder)
4. `{cwd}/afsextracted/` (folder)

**Linux**:
1. `~/.local/share/CrowdedStreet/3SX/resources/SF33RD.AFS` (archive)
2. `{cwd}/SF33RD.AFS` (archive)
3. `~/.local/share/CrowdedStreet/3SX/resources/afsextracted/` (folder)
4. `{cwd}/afsextracted/` (folder)

Place your `SF33RD.AFS` file or extracted files in one of these locations.

## Project Structure

*   `sf33rd/`: The core Python package for the project.
    *   `core/`: Core data models, libraries, and utilities.
    *   `parsers/`: Parsers for the various file formats used in the game.
    *   `lib/`: Palette and animation libraries.
*   `SF3FSPLORERGUI/`: The GUI application package.
*   `run_character_editor.py`: Launcher for the Character Extractor GUI.
*   `output/`: The default directory where extracted assets will be saved.

## Troubleshooting

*   **Missing Files**: Ensure your `SF33RD.AFS` file is in one of the data source locations listed above.
*   **Crashes or Errors**: Check that you have read and write permissions for the `output` directory.
*   **Dependencies**: If using pip, ensure all dependencies are installed with `pip install .`.
*   **uv Issues**: Try `uv sync` to refresh dependencies.

## Disclaimer

**Use at Your Own Risk**

This tool is provided "as is" without any warranties or guarantees. The authors and contributors are not responsible for:

- Any damage to your system, files, or data
- Issues with your Python environment or virtual environments
- Problems caused by incorrect installation or usage
- Any other consequences resulting from the use of this tool

**User Responsibility**

You are solely responsible for:
- Ensuring your Python environment is properly configured
- Managing your virtual environments (if used)
- Installing dependencies correctly
- Following the installation and usage instructions
- Any modifications you make to the tool or its dependencies

**No Liability**

By using this tool, you acknowledge and agree that:
- You understand the risks involved
- You will not hold the authors or contributors liable for any damages
- You will use the tool responsibly and legally
- You are responsible for any issues that may arise from its use

**Recommendations**

- Always backup important data before using the tool
- Consider using a virtual environment to isolate dependencies
- Test the tool with non-critical files first
- Report any issues or bugs you encounter

## License

This tool is based on research and reverse engineering for the Street Fighter III community. Please respect game licensing and use this tool only with legally owned game files.
