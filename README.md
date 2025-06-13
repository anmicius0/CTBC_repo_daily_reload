# IQ server <-> Azure Repo Sync & Cleanup Tool 🚀

This package includes two main tools:

1.  **Sync Tool:**
    - Finds your Azure DevOps repositories.
    - Creates matching applications in Sonatype IQ Server if they don't exist.
    - Triggers a new security scan for these applications.
2.  **Cleanup Tool:**
    - A powerful tool to **delete ALL applications** within the organizations you define in your settings.
    - **⚠️ USE WITH EXTREME CAUTION!** Deletions are permanent.

## 🚀 Getting Started (For Users)

### 1. 📥 Download the Tools

- Go to the **GitHub Releases page** for this project.
- Download the file appropriate for your computer:
  - **Windows:** Look for `repo-sync-windows.zip`
  - **macOS:** Look for `repo-sync-macos.tar.gz`
  - **Linux:** Look for `repo-sync-linux.tar.gz`
- **Extract the downloaded file.** You'll find a folder (e.g., `repo-sync-windows`) containing:
  - `repo-sync` (or `repo-sync.exe` for Windows)
  - `repo-cleanup` (or `repo-cleanup.exe` for Windows)
  - A `config/` folder (very important for settings!)
  - Other files you can ignore for now (like `pyproject.toml`, `README.md`).

### 2. 🔑 Set Up Your Credentials (`config/.env`)

The tools need to know how to connect to Azure DevOps and your IQ Server.

- Inside the extracted folder, go into the `config/` directory.
- You'll see a file named `.env.example`. **Make a copy of this file and rename the copy to simply `.env`** (make sure it doesn't have any extra extensions like `.txt`).
- Open `config/.env` with a text editor (like Notepad on Windows, TextEdit on macOS, or VS Code).
- Fill in your details for each line. Here's what they mean:

  ```dotenv
  # Azure DevOps Configuration
  AZURE_DEVOPS_TOKEN=your_azure_devops_personal_access_token_here  # Get this from Azure DevOps (see below!)
  AZURE_DEVOPS_ORGANIZATION=your_organization_name                 # Your Azure DevOps organization name (e.g., "ctbcbank")

  # IQ Server Configuration
  IQ_SERVER_URL=http://your-iq-server-url:8070/                    # The full URL to your IQ Server (e.g., "http://iq.ctbc.com:8070/")
  IQ_USERNAME=your_iq_username                                     # Your username for IQ Server
  IQ_PASSWORD=your_iq_password                                     # Your password for IQ Server

  # Application Configuration (Optional, default values are usually fine)
  DEFAULT_BRANCH=main    # The default branch name to scan (e.g., "main", "master")
  STAGE_ID=source        # The IQ Server stage for source code scans (e.g., "source", "build")
  DEBUG=false            # Set to 'true' for more detailed logs (helpful for troubleshooting)
  LOG_LEVEL=INFO         # Level of detail in logs (INFO, DEBUG, WARNING, ERROR)
  ```

### 3. 🏢 Check Your Organizations (`config/org-azure.json`)

The tools use this file to know which Sonatype IQ organizations to work with.

- Open `config/org-azure.json` with a text editor.
- **Important:** Both the Sync and Cleanup tools will **only process organizations that have both an `"id"` and a `"chineseName"`**.
- Verify that the `id` values match your Sonatype IQ organization IDs, and that `chineseName` correctly identifies your departments in Chinese. The Sync tool uses this `chineseName` to match with descriptions in Azure DevOps projects.

  _Example of a valid entry:_

  ```json
  {
    "id": "0a4006e9236c4ede89cfec9a25211e02",
    "name": "Application Service Development Dept",
    "chineseName": "後勤應用系統部"
  }
  ```

  _Entries without `"chineseName"` (like "CTBC-Default") will be ignored by both tools._

### 🔄 Sync Tool (`repo-sync`)

This tool is designed to be run regularly to keep your IQ Server up-to-date.

1.  **Open your terminal or command prompt.**
2.  **Navigate to the directory** where you extracted the tools.
    - **Example (Linux/macOS):** `cd /path/to/your/extracted/folder`
    - **Example (Windows):** `cd C:\path\to\your\extracted\folder`
3.  **Run the Sync Tool:**

    - **Linux/macOS:**
      ```bash
      ./repo-sync
      ```
    - **Windows (Command Prompt):**
      ```cmd
      repo-sync.exe
      ```
    - **Windows (PowerShell):**
      ```powershell
      .\repo-sync.exe
      ```

    The tool will start showing its progress in the terminal.

### 🧹 Cleanup Tool (`repo-cleanup`)

This tool is for deleting applications in bulk. **Be extremely careful!**

1.  **Open your terminal or command prompt.**
2.  **Navigate to the directory** where you extracted the tools.
3.  **Review `config/org-azure.json` one last time!** Ensure it only contains the organizations you truly want to clean up. Remember, only organizations with `chineseName` will be processed.
4.  **Run the Cleanup Tool:**

    - **Linux/macOS:**
      ```bash
      ./repo-cleanup
      ```
    - **Windows (Command Prompt):**
      ```cmd
      repo-cleanup.exe
      ```
    - **Windows (PowerShell):**
      ```powershell
      .\repo-cleanup.exe
      ```

    The tool will list the applications it's deleting.

## 🛠️ For Developers (Codebase Maintenance & Customization)

If you want to modify, contribute to, or simply understand how these tools work, this section is for you.

### ⚙️ Setting Up Your Development Environment

This project uses `uv` for super-fast Python dependency management.

1.  **Install `uv`**
2.  **Get the Code:**
3.  **Create and Activate Virtual Environment:** This keeps your project's dependencies separate from your system's Python.
    ```bash
    uv venv
    ```
4.  **Install Dependencies:** This command installs everything listed in `pyproject.toml` and locks it in `uv.lock`.
    ```bash
    uv sync
    ```

### 📂 Project Structure Explained

- `sync_repos.py`: This is the brain of the Sync Tool. All logic for finding Azure DevOps repos, creating IQ applications, and triggering scans is here.
- `cleanup_tool.py`: This is the brain of the Cleanup Tool. It contains the logic for finding and deleting IQ applications.
- `error_handler.py`: A small file that helps catch and log errors consistently.
- `config/`: This folder holds all user-facing settings (`.env`, `org-azure.json`, etc.). When you build the executables, this entire folder is bundled with them.
- `pyproject.toml`: Defines project information and lists all Python libraries (dependencies) that this project needs.
- `uv.lock`: This file is automatically generated by `uv sync`. It precisely records the exact versions of every dependency used, ensuring consistent builds across different machines. **Always commit this file!**
- `.github/workflows/`: Contains the GitHub Actions files (`build-release.yml`) that automate the process of building the standalone executables and creating releases whenever new code is pushed.

### 🏗️ Building the Executables Locally (Advanced)

The official releases are built automatically by GitHub Actions, but you can build them on your own machine if needed.

1.  **Ensure your development environment is set up** (see above, including `uv venv` and `uv sync`).
2.  **Install `pyinstaller`** (the tool that turns Python scripts into standalone executables):
    ```bash
    uv pip install pyinstaller
    ```
3.  **Run the build commands:**

- **Build the Sync Tool:**

  ```bash
  uv run pyinstaller \
    --onefile \
    --name repo-sync \
    --add-data="config:config" \
    --hidden-import=dotenv \
    --hidden-import=requests \
    --hidden-import=base64 \
    --clean \
    sync_repos.py
  ```

- **Build the Cleanup Tool:**
  ```bash
  uv run pyinstaller \
    --onefile \
    --name repo-cleanup \
    --add-data="config:config" \
    --hidden-import=dotenv \
    --hidden-import=requests \
    --clean \
    cleanup_tool.py
  ```

4.  Your newly built executables will be located in the `dist/` directory.

## 📄 License

This project is licensed under the MIT License.
