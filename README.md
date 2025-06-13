# Nexus Manager

## 📝 Overview

Nexus Manager is a cross-platform tool for managing Nexus Repository and IQ Server, providing both a web interface and a CLI. It is distributed as a standalone executable for Windows, macOS, and Linux.
This means you do not need Python or `uv` installed to run the downloaded application.

---

## 📦 Using the Release Executable

### 1. Download & Extract

- Download the appropriate archive for your platform from the release page.
- Extract the archive. You will get a folder containing:
  - The executable (`nexus-manager` or `nexus-manager.exe`)
  - `config/` (configuration files)
  - `templates/` (web UI templates)
  - `pyproject.toml`
  - `README.md`
The `pyproject.toml` file is included for development purposes; `uv` is used for building the executable and managing dependencies if you plan to modify the code, but it's not needed to run the pre-compiled application.

### 2. Configure Environment

- Copy `config/.env.example` to `config/.env` and fill in your server details and secrets.

### 3. Run the Application

- **Web UI:**
  - On Linux/macOS: `./nexus-manager`
  - On Windows: `nexus-manager.exe`
- **CLI:**
  - On Linux/macOS: `./nexus-manager cli`
  - On Windows: `nexus-manager.exe cli`

---

## 🎨 Customization

### Configuration

- All configuration is in the `config/` directory.
- Edit `config/.env` for environment variables (see `.env.example` for options).
- Edit `config/organisations.json` and `config/package_manager_config.json` for organization and package manager settings.

### Web Templates

- The web UI uses Jinja2 templates in the `templates/` directory.
- Customize `index.html` and `result.html` as needed.

---

## 🛠️ Codebase Maintenance

### ⚙️ Setting Up a Development Environment

- 1. Install [uv](https://github.com/astral-sh/uv) if you haven't already.
- 2. Clone this repository.
- 3. Navigate to the repository directory.
- 4. Create a virtual environment: `uv venv`
- 5. Activate the virtual environment: `source .venv/bin/activate` (Linux/macOS) or `.venv\Scripts\activate` (Windows).
- 6. Install dependencies: `uv pip install -e .[dev]` (Install in editable mode with development extras. Adjust if your project uses a different way to specify extras or if there are no dev extras).

### Structure

- `nexus_manager.py`: Main entry point.
- `nexus_manager/`: Core logic and utilities.
  - `core.py`: Main business logic.
  - `utils.py`: Helper functions.
  - `error_handler.py`: Error handling.
- `config/`: Configuration files.
- `templates/`: Web UI templates.

### Adding Features

- Add new logic in `nexus_manager/` as needed.
- Register new CLI commands or web routes in `nexus_manager.py` or `core.py`.
- Update templates for UI changes.

### 📦 Dependency Management with uv

- Dependencies are managed with [uv](https://github.com/astral-sh/uv) and listed in `pyproject.toml`.
- To add a dependency: `uv pip install <package>`
  - `pyproject.toml` may need manual editing for version constraints or extras.
- To remove a dependency: `uv pip uninstall <package>`
- After modifying dependencies, `uv` will automatically update `uv.lock` if you run an install or sync command. Commit both `pyproject.toml` and `uv.lock`.

### 🏗️ Building the Executable with uv

- Builds are automated via GitHub Actions.
- To build locally:
  1. Ensure you have [uv](https://github.com/astral-sh/uv) and [pyinstaller](https://pyinstaller.org/) installed in your environment (e.g., `uv pip install pyinstaller`).
  2. Run the build command as in `.github/workflows/build-release.yml`. The workflow file might contain specific `uv` commands for building.

---

## 💬 Support

- For issues, open a GitHub issue in this repository.
- For configuration help, see comments in `config/.env.example`.

---

## 📄 License

See `LICENSE` file (if present) for license information.
