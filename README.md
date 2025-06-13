# GitHub to IQ Server Sync Tool

Automatically synchronizes GitHub repositories with Sonatype IQ Server - creates applications, adds SCM connections, and triggers security scans.

## Quick Start

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

2. **Configure environment:**

```bash
cp .env.example .env
# Edit .env with your credentials
```

3. **Run:**

```bash
python main.py
```

## Configuration

### Required Environment Variables

The tool uses a `.env` file for configuration. You can customize its behavior by editing this file. When running as an executable, make sure the `.env` file is in the same directory as the executable or in your working directory.

```bash
GITHUB_TOKEN=your_github_token
IQ_SERVER_URL=https://your-iq-server.com
IQ_USERNAME=your_username
IQ_PASSWORD=your_password
ORGANIZATION_ID=your_org_id
REPOSITORY_SEARCH_TERM=your_search_term    # Search term for repos
```

### Optional Settings

```bash
DEFAULT_BRANCH=main               # Default branch name
STAGE_ID=source                   # IQ scan stage
```

## Customization with Executable

When running the tool as an executable (e.g., a frozen binary), you can still customize its behavior using the following files:

### 1. `.env` File

- Place your `.env` file in the same directory as the executable or in your current working directory.
- Edit the variables to set your GitHub token, IQ Server credentials, default branch, scan stage, and search query.
- Example:

```bash
GITHUB_TOKEN=your_github_token
IQ_SERVER_URL=https://your-iq-server.com
IQ_USERNAME=your_username
IQ_PASSWORD=your_password
DEFAULT_BRANCH=main
STAGE_ID=source
GITHUB_SEARCH_QUERY="權責部門：{kw}" in:description user:{user}
```

### 2. `org-github.json` File

- This file maps organization IDs to their names and (optionally) Chinese names.
- Place `org-github.json` in the same directory as the executable or working directory.
- To customize which organizations are processed, edit this file to add, remove, or modify organization entries.
- Example entry:

```json
[
  {
    "id": "0a4006e9236c4ede89cfec9a25211e02",
    "name": "Application Service Development Dept",
    "chineseName": "後勤應用系統部"
  }
]
```

## Customization

### Search Criteria

Modify search term in `.env`:

```bash
REPOSITORY_SEARCH_TERM=myproject  # Find repos with "myproject" in name
```

Or customize the search query using `GITHUB_SEARCH_QUERY` in `.env`:

```bash
GITHUB_SEARCH_QUERY="權責部門：{kw}" in:description user:{user}
```

### Repository Filtering

Edit `get_repositories()` in `main.py` to add custom filters:

```python
def get_repositories(self):
    # Add custom filtering logic here
    search_results = self.github.search_repositories(
        query=f"{self.config['SEARCH_TERM']} in:name user:{user.login}"
    )
    # Filter results as needed
    return filtered_repos
```

### IQ Server Settings

Configure scan behavior:

```bash
STAGE_ID=build     # Change scan stage
DEFAULT_BRANCH=dev # Use different default branch
```

## Maintenance

### Key Components

- **`get_config()`**: Environment variable loading
- **`IQServerClient`**: IQ Server API interactions
- **`GitHubRepoSync`**: Main sync orchestration

### Common Tasks

**Add new environment variables:**

```python
# In get_config()
config = {
    # ...existing...
    "NEW_SETTING": os.getenv("NEW_SETTING", "default"),
}
```

**Modify repository search:**

```python
# In get_repositories()
search_results = self.github.search_repositories(
    query=f"your_custom_query"
)
```

**Add error handling:**

```python
try:
    # API call
except Exception as e:
    print(f"Error: {e}")
    errors += 1
```

### Troubleshooting

- **Auth issues**: Verify GitHub token permissions and IQ Server credentials
- **Rate limits**: GitHub allows 5000 requests/hour for authenticated users
- **Network errors**: Check IQ Server URL and network connectivity

### Logging

Enable debug mode by setting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
