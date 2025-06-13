# GitHub to IQ Server Sync Tool

Automatically synchronizes GitHub repositories with Sonatype IQ Server - creates applications, adds SCM connections, and triggers security scans for multiple organizations.

## 🚀 Quick Start

1. **Install dependencies:**

```bash
uv pip install -r requirements.txt
```

2. **Configure your environment:**

```bash
# Edit config/.env with your credentials
nano config/.env
```

3. **Set up organizations:**

```bash
# Edit config/org-github.json or config/org-github.json
nano config/org-github.json
```

4. **Run the sync:**

```bash
uv run main.py        # Main sync tool
uv run debug.py       # Cleanup tool (deletes all apps)
```

## ⚙️ Configuration Files

### 1. Environment Configuration (`config/.env`)

**Required settings:**

```bash
GITHUB_TOKEN=github_pat_your_token_here
IQ_SERVER_URL=http://your-iq-server:8070/
IQ_USERNAME=your_iq_username
IQ_PASSWORD=your_iq_password
```

**Optional settings:**

```bash
DEFAULT_BRANCH=main                                    # Default branch for repos
STAGE_ID=source                                       # IQ scan stage (source/build/stage-release)
GITHUB_SEARCH_QUERY="權責部門：{kw}" in:description user:{user}  # Custom search query
```

### 2. Organization Configuration

Choose one of these files to define which organizations to process:

**For production:** `config/org-github.json`
**For testing:** `config/org-github.json`

**File format:**

```json
[
  {
    "id": "organization-uuid-here",
    "name": "English Department Name",
    "chineseName": "中文部門名稱"
  }
]
```

**Note:** Only organizations with a `chineseName` field will be processed.

## 📖 How to Use

### Basic Operation

The tool operates in two main modes:

1. **Sync Mode (`main.py`)**: Creates applications and triggers scans
2. **Cleanup Mode (`debug.py`)**: Deletes all applications in specified organizations

### Workflow

1. **First run**: Use `org-github.json` for testing with a small subset of organizations
2. **Testing**: Run `uv run main.py` to verify everything works correctly
3. **Cleanup**: Run `uv run debug.py` to remove test applications
4. **Production**: Switch to `org-github.json` and run `uv run main.py` for full sync

### Understanding the Output

```
=== 🏢 Syncing organization: CTBC (ID: dba7d9ddcbd04fc787b2bc81ec519b3b) ===
  🟢 [1/5] Created & scanned: my-repo-1
  🔄 [2/5] Scanned existing: my-repo-2
  ❌ [3/5] my-repo-3 - 404 Client Error: Not Found
--- CTBC summary: 🟢 2 created, 🔄 3 scanned, ❌ 1 errors ---
```

- 🟢 **Created**: New application created and scanned
- 🔄 **Scanned**: Existing application re-scanned
- ❌ **Error**: Failed to process (check permissions, network, etc.)

## 🎨 Customization

### 1. Change Repository Search Criteria

**Method A: Simple search term**

```bash
# In .env file
REPOSITORY_SEARCH_TERM=myproject
```

**Method B: Custom search query**

```bash
# In .env file - more flexible
GITHUB_SEARCH_QUERY="topic:security language:python user:{user}"
GITHUB_SEARCH_QUERY="created:>2023-01-01 user:{user}"
GITHUB_SEARCH_QUERY="myproject in:name user:{user}"
```

**Method C: Code modification**
Edit the `repos()` method in `main.py`:

```python
def repos(self, kw):
    user = self.gh.get_user()

    # Option 1: Search by topic
    query = f"topic:{kw.lower()} user:{user.login}"

    # Option 2: Search by description with custom format
    query = f"\"Department: {kw}\" in:description user:{user.login}"

    # Option 3: Complex search with multiple criteria
    query = f"{kw} in:name,description language:python user:{user.login}"

    # Option 4: Date-based filtering
    query = f"created:>2023-01-01 pushed:>2023-12-01 user:{user.login}"

    return [/* ...existing code... */]
```

### 2. Modify Application Creation Logic

Edit the `create()` method in the `IQ` class to customize application settings:

```python
def create(self, n, url, br, oid):
    # Customize application creation
    app_data = {
        "publicId": n.lower().replace(" ", "-"),
        "name": f"[PROD] {n}",  # Add prefix
        "organizationId": oid,
        # Add custom tags
        "tags": [
            {"name": "source", "value": "github-sync"},
            {"name": "environment", "value": "production"}
        ]
    }

    a = self.req("POST", "/api/v2/applications", json=app_data).json()["id"]

    # Customize SCM settings
    scm_data = {
        "repositoryUrl": url,
        "baseBranch": br,
        "remediationPullRequestsEnabled": True,
        "pullRequestCommentingEnabled": True,
        "sourceControlEvaluationsEnabled": True,
        # Add custom SCM settings
        "enablePullRequestComments": True,
        "pullRequestCommentBehavior": "NEW_AND_UPDATED_ISSUES"
    }

    # ...existing code...
```

### 3. Add Custom Repository Filtering

```python
def repos(self, kw):
    # ...existing search code...

    repos = []
    for r in self.gh.search_repositories(query=q):
        # Filter by file types
        if any(r.name.endswith(ext) for ext in ['-api', '-service', '-app']):
            continue

        # Filter by size (skip very large repos)
        if r.size > 100000:  # 100MB+
            continue

        # Filter by activity (skip inactive repos)
        if r.pushed_at < datetime.now() - timedelta(days=365):
            continue

        # Filter by language
        if r.language not in ['Python', 'Java', 'JavaScript']:
            continue

        repos.append({
            "name": r.name,
            "clone_url": r.clone_url,
            "default_branch": r.default_branch or self.c["DEFAULT_BRANCH"],
        })

    return repos
```

### 4. Environment-Specific Configuration

Create different config files for different environments:

**config/.env.dev**

```bash
IQ_SERVER_URL=http://dev-iq-server:8070/
STAGE_ID=build
DEFAULT_BRANCH=develop
```

**config/.env.prod**

```bash
IQ_SERVER_URL=http://prod-iq-server:8070/
STAGE_ID=source
DEFAULT_BRANCH=main
```

Then load the appropriate config:

```python
# Load environment-specific config
env_file = "config/.env.prod" if sys.argv[1] == "prod" else "config/.env.dev"
load_dotenv(resolve_path(env_file))
```

### 5. Add Batch Processing

```python
def sync_batch(self, orgs, batch_size=5):
    """Process organizations in batches to avoid rate limits"""
    for i in range(0, len(orgs), batch_size):
        batch = orgs[i:i + batch_size]
        print(f"\n📦 Processing batch {i//batch_size + 1}/{(len(orgs)-1)//batch_size + 1}")

        for org in batch:
            self.sync(org["id"], org["chineseName"])

        # Rate limiting pause between batches
        if i + batch_size < len(orgs):
            print("⏳ Waiting 30 seconds between batches...")
            time.sleep(30)
```

## 🔧 Maintenance

### Key Architecture

The codebase is organized into three main components:

1. **Configuration (`CFG()`, `ORG()`)**: Loads environment and organization settings
2. **API Clients (`IQ`, `Github`)**: Handles external API interactions
3. **Orchestration (`Sync`)**: Coordinates the sync process

### Common Maintenance Tasks

#### Adding New Environment Variables

```python
def CFG():
    return {
        # ...existing variables...
        "NEW_SETTING": os.getenv("NEW_SETTING", "default_value"),
        "TIMEOUT": int(os.getenv("TIMEOUT", "30")),
        "RETRY_COUNT": int(os.getenv("RETRY_COUNT", "3")),
    }
```

#### Adding Error Handling and Retries

```python
import time
from functools import wraps

def retry(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    print(f"⚠️  Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
            return wrapper
        return decorator

# Apply to methods
class IQ:
    @retry(max_attempts=3)
    def req(self, m, e, **k):
        # ...existing code...
```

#### Adding Logging

```python
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync.log'),
        logging.StreamHandler()
    ]
)

# Use in code
class Sync:
    def __init__(self, c):
        self.logger = logging.getLogger(self.__class__.__name__)
        # ...existing code...

    def sync(self, oid, kw):
        self.logger.info(f"Starting sync for {kw} (ID: {oid})")
        # ...existing code...
        self.logger.info(f"Completed sync for {kw}: {cr} created, {sc} scanned, {er} errors")
```

#### Adding Progress Tracking

```python
from tqdm import tqdm

def sync(self, oid, kw):
    repos = self.repos(kw)
    apps = self.iq.apps(oid)

    with tqdm(total=len(repos), desc=f"Processing {kw}") as pbar:
        for r in repos:
            try:
                # ...existing processing...
                pbar.set_postfix({"current": r["name"]})
            except Exception as e:
                pbar.set_postfix({"error": str(e)[:50]})
            finally:
                pbar.update(1)
```

#### Health Checks and Validation

```python
def validate_config(self):
    """Validate configuration before starting sync"""
    required = ["GITHUB_TOKEN", "IQ_SERVER_URL", "IQ_USERNAME", "IQ_PASSWORD"]
    missing = [k for k in required if not self.c.get(k)]

    if missing:
        raise ValueError(f"Missing required config: {', '.join(missing)}")

    # Test API connections
    try:
        self.gh.get_user()
        print("✅ GitHub connection OK")
    except Exception as e:
        raise ValueError(f"GitHub connection failed: {e}")

    try:
        self.iq.req("GET", "/api/v2/organizations")
        print("✅ IQ Server connection OK")
    except Exception as e:
        raise ValueError(f"IQ Server connection failed: {e}")

def main():
    c = CFG()
    s = Sync(c)
    s.validate_config()  # Add validation
    # ...rest of main...
```

### Troubleshooting Guide

| Issue                          | Solution                                                                                    |
| ------------------------------ | ------------------------------------------------------------------------------------------- |
| **Authentication errors**      | Verify tokens have correct permissions: `repo` scope for GitHub, admin access for IQ Server |
| **Rate limiting**              | Add delays between requests, implement exponential backoff                                  |
| **Network timeouts**           | Increase timeout values, add retry logic                                                    |
| **Large repositories**         | Filter by repository size, implement pagination                                             |
| **Missing repositories**       | Check search query syntax, verify organization access                                       |
| **Application creation fails** | Verify organization IDs, check IQ Server permissions                                        |

### Performance Optimization

```python
# Concurrent processing
import concurrent.futures
import threading

class Sync:
    def __init__(self, c):
        # ...existing code...
        self.thread_lock = threading.Lock()

    def sync_concurrent(self, orgs, max_workers=5):
        """Process multiple organizations concurrently"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.sync, org["id"], org["chineseName"]): org
                for org in orgs
            }

            for future in concurrent.futures.as_completed(futures):
                org = futures[future]
                try:
                    result = future.result()
                    print(f"✅ Completed {org['chineseName']}")
                except Exception as e:
                    print(f"❌ Failed {org['chineseName']}: {e}")
```

### Development Best Practices

1. **Test with org-github.json first**: Always test changes with a small set of organizations
2. **Use version control**: Track changes to configuration files
3. **Monitor API rate limits**: GitHub allows 5000 requests/hour for authenticated users
4. **Implement graceful failures**: Don't let one failed repository stop the entire sync
5. **Add comprehensive logging**: Essential for debugging production issues
6. **Validate inputs**: Check configuration and API responses before processing

### Adding New Features

To add new features, follow this pattern:

1. **Add configuration options** in `CFG()`
2. **Extend API clients** (`IQ`, GitHub) as needed
3. **Modify orchestration logic** in `Sync` class
4. **Add error handling** and logging
5. **Update documentation** and examples
6. **Test thoroughly** with debug configuration first
