# CTBC Repo Sync & Cleanup Tool 🚀

## 📝 Overview

This project provides a suite of command-line tools to streamline the management of applications in **Sonatype IQ Server**, tailored for CTBC's workflow. The tools are distributed as cross-platform, standalone executables for Windows, macOS, and Linux, which means **you do not need Python installed to run them**.

The suite includes two main utilities:

- **🔄 Sync Tool (`ctbc-repo-sync`):** Automatically discovers GitHub repositories based on a specific description tag (`權責部門：...`), creates corresponding applications in Sonatype IQ Server if they don't already exist, and triggers a new scan.
- **🧹 Cleanup Tool (`ctbc-repo-cleanup`):** A powerful utility to bulk-delete all applications within the organizations defined in your configuration. Use with caution!

---

## 🚀 Getting Started

Follow these steps to get the tools up and running in minutes.

### 1. 📥 Download & Extract

- Navigate to the [**GitHub Releases page**](https://github.com/your-repo/releases) for this project.
- Download the appropriate archive for your operating system (`.zip` for Windows, `.tar.gz` for macOS/Linux).
- Extract the archive. You will find a folder containing:
  - `ctbc-repo-sync` or `ctbc-repo-sync.exe`
  - `ctbc-repo-cleanup` or `ctbc-repo-cleanup.exe`
  - `config/` (Directory for your configuration files)
  - `pyproject.toml` (For development purposes)
  - `README.md` (This file!)

### 2. 🔑 Configure Your Environment

The tools require credentials to access GitHub and your IQ Server.

- In the `config/` directory, make a copy of `.env.example` and name it `.env`.
- Open `config/.env` and fill in your details:

  ```dotenv
  # GitHub Configuration
  GITHUB_TOKEN=your_github_personal_access_token

  # IQ Server Configuration
  IQ_SERVER_URL=http://your-iq-server-url:8070/
  IQ_USERNAME=your_iq_username
  IQ_PASSWORD=your_iq_password

  # Application Configuration (optional)
  DEFAULT_BRANCH=main
  STAGE_ID=source
  DEBUG=false
  ```

### 3. 🏢 Configure Organizations

The tools operate on a list of organizations defined in `config/org-github.json`. Both the Sync and Cleanup tools will only process organizations that have a `chineseName` key.

- Verify that `config/org-github.json` contains the correct IQ Organization IDs and department names (`chineseName`).

---

## 💻 How to Use the Tools

Once configured, you can run the tools directly from your terminal.

### 🔄 Sync Tool (`ctbc-repo-sync`)

This is the primary tool for keeping Sonatype IQ Server synchronized with your GitHub repositories. It will:

1.  Search GitHub for repositories matching the `chineseName` from your config file.
2.  Check if a corresponding application exists in IQ Server.
3.  Create a new application if it's missing.
4.  Trigger a source code scan for all found repositories.

**To run the Sync Tool:**

- **Linux/macOS:**
  ```bash
  ./ctbc-repo-sync
  ```
- **Windows:**
  ```powershell
  .\ctbc-repo-sync.exe
  ```

### 🧹 Cleanup Tool (`ctbc-repo-cleanup`)

This utility helps you perform housekeeping by removing applications from IQ Server.

⚠️ **Warning:** This is a **destructive operation**. It will permanently delete all applications within the configured organizations. Please double-check your `config/org-github.json` file before running.

**To run the Cleanup Tool:**

- **Linux/macOS:**
  ```bash
  ./ctbc-repo-cleanup
  ```
- **Windows:**
  ```powershell
  .\ctbc-repo-cleanup.exe
  ```

---

## 🛠️ For Developers (Codebase Maintenance)

Want to contribute or modify the tools? Here’s how to set up a development environment.

### ⚙️ Setting Up the Environment

This project uses [**uv**](https://github.com/astral-sh/uv) for fast dependency and environment management.

1.  Install `uv` by following the [official instructions](https://github.com/astral-sh/uv#installation).
2.  Clone this repository: `git clone <repository-url>`
3.  Navigate into the project directory.
4.  Create a virtual environment: `uv venv`
5.  Activate it:
    - Linux/macOS: `source .venv/bin/activate`
    - Windows: `.venv\Scripts\activate`
6.  Install all dependencies from the lock file: `uv sync`

### 📂 Project Structure

- `sync_repos.py`: Main entrypoint for the repository synchronization tool.
- `cleanup_tool.py`: Main entrypoint for the application cleanup tool.
- `error_handler.py`: Centralized error handling logic for robust operations.
- `config/`: Contains all user-facing configuration files.
- `pyproject.toml`: Defines project metadata and dependencies.
- `uv.lock`: Lockfile for reproducible dependency installation with `uv`.
- `.github/workflows/`: Contains the GitHub Actions workflow for building release executables.

### 📦 Dependency Management with `uv`

- To add a new dependency: `uv pip install <package-name>`
- To remove a dependency: `uv pip uninstall <package-name>`
- After changing dependencies in `pyproject.toml`, run `uv pip sync` to update your environment and `uv.lock`. Always commit both `pyproject.toml` and `uv.lock`.

### 🏗️ Building the Executables

Builds are handled automatically by the `.github/workflows/build-release.yml` workflow. To build the executables locally:

1.  Make sure you have `uv` and are inside the activated virtual environment.
2.  Install `pyinstaller`: `uv pip install pyinstaller`
3.  Run the build command for each tool. For example:

    ```bash
    # Build the Sync Tool
    uv run pyinstaller \
      --onefile \
      --name ctbc-repo-sync \
      --add-data="config:config" \
      --hidden-import=github \
      --hidden-import=dotenv \
      --hidden-import=requests \
      --clean \
      sync_repos.py

    # Build the Cleanup Tool
    uv run pyinstaller \
      --onefile \
      --name ctbc-repo-cleanup \
      --add-data="config:config" \
      --hidden-import=github \
      --hidden-import=dotenv \
      --hidden-import=requests \
      --clean \
      cleanup_tool.py
    ```

4.  Your executables will be in the `dist/` directory.

---

## 💬 Support

If you encounter a problem or have a suggestion, please [open an issue](https://github.com/your-repo/issues) on GitHub.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
