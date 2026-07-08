# Google Drive Plugin — Google API Reference

## Authentication: Service Accounts

### What Is a Service Account?

A service account is a Google Cloud identity used by applications (not humans). It authenticates using a private key in a JSON file — no browser-based OAuth consent flow required.

### Setup Steps (for documentation — user does this manually)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable the **Google Drive API** and **Google Docs API**
4. Go to **IAM & Admin → Service Accounts**
5. Create a new service account
6. Create a key (JSON format) — download the `.json` file
7. **Share the target Google Drive folder** with the service account's email address (e.g., `wikiknowledge@project-id.iam.gserviceaccount.com`) with at least "Viewer" role (or "Editor" if bidirectional metadata is needed)

### Authentication in Python

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",      # Read files & metadata
    "https://www.googleapis.com/auth/drive.appdata",        # appProperties access
]

# For bidirectional mode, replace drive.readonly with:
SCOPES_BIDIRECTIONAL = [
    "https://www.googleapis.com/auth/drive",                # Full Drive access (for appProperties write)
]

credentials = service_account.Credentials.from_service_account_file(
    "path/to/service-account.json",
    scopes=SCOPES,
)

drive_service = build("drive", "v3", credentials=credentials)
```

### Important: Scopes

| Mode | Scope | Reason |
|------|-------|--------|
| Read-only | `drive.readonly` | List files, read metadata, export content |
| Bidirectional | `drive` | Also write `appProperties` on files |
| appProperties | `drive.appdata` | May be needed for appProperties on some configurations |

Note: `drive.readonly` is sufficient for reading `appProperties` that were set by this service account. Writing `appProperties` requires `drive` scope.

## Google Drive API — Key Operations

### List Files in a Folder

```python
results = drive_service.files().list(
    q="'FOLDER_ID' in parents and trashed = false",
    fields="nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, webViewLink, appProperties)",
    pageSize=1000,
    orderBy="modifiedTime desc",
).execute()

files = results.get("files", [])
next_page_token = results.get("nextPageToken")
```

#### Query Syntax for `q` Parameter

| Query | Meaning |
|-------|---------|
| `'FOLDER_ID' in parents` | Files directly in this folder |
| `trashed = false` | Exclude trashed files |
| `mimeType = 'application/vnd.google-apps.document'` | Only Google Docs |
| `mimeType = 'application/vnd.google-apps.folder'` | Only folders (for recursive listing) |

For recursive listing, we need to walk folders manually — the Drive API does not support recursive queries natively.

#### File Fields We Need

| Field | Purpose |
|-------|---------|
| `id` | Unique document ID (stable across renames/moves) |
| `name` | Document title |
| `mimeType` | To filter Google Docs from other file types |
| `modifiedTime` | For delta sync — compare with cached value |
| `createdTime` | For `ArticleMeta.created` |
| `webViewLink` | For the footer link back to Google Drive |
| `appProperties` | For reading `wk_tags` and `wk_categories` |

### Export Google Doc as Markdown

```python
from googleapiclient.http import MediaIoBaseDownload
import io

request = drive_service.files().export(
    fileId="DOC_ID",
    mimeType="text/markdown",
)

content = request.execute()
# content is bytes — decode to string
markdown_text = content.decode("utf-8")
```

#### Supported Export MIME Types for Google Docs

| MIME Type | Format |
|-----------|--------|
| `text/markdown` | Markdown (best option for our use case) |
| `text/html` | HTML (can be converted to markdown via `markdownify`) |
| `text/plain` | Plain text (loses formatting) |
| `application/pdf` | PDF (not useful for us) |
| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | DOCX |

**Primary choice**: `text/markdown` — direct export, no conversion needed.

**Fallback**: `text/html` → convert with `markdownify` library if markdown export quality is poor (known to have issues with complex formatting like nested tables).

> **Note**: The `text/markdown` export MIME type was added relatively recently to the Google Drive API. If it's unavailable or produces poor results, fall back to HTML export + markdownify conversion. The implementation should try markdown first and fall back gracefully.

### Update File Properties (Bidirectional)

```python
drive_service.files().update(
    fileId="DOC_ID",
    body={
        "appProperties": {
            "wk_tags": "architecture, design",
            "wk_categories": "system-architecture"
        }
    },
    fields="id, appProperties",
).execute()
```

#### appProperties Limits

- Max 30 key-value pairs per file
- Max key length: 124 bytes
- Max value length: 124 bytes (approximately 120 ASCII characters)
- Private to the app (service account project) that set them

**Implication for our design**: Category and tag lists must fit in ~120 characters each. If they exceed this, we should truncate with a warning. In practice, this is rarely an issue — a list like `"system-architecture, api-docs, deployment"` is 47 characters.

### Pagination

The Drive API returns paginated results. Always handle `nextPageToken`:

```python
all_files = []
page_token = None

while True:
    results = drive_service.files().list(
        q=query,
        fields="nextPageToken, files(...)",
        pageSize=1000,
        pageToken=page_token,
    ).execute()
    
    all_files.extend(results.get("files", []))
    page_token = results.get("nextPageToken")
    
    if not page_token:
        break
```

## Google Docs MIME Types Reference

| MIME Type | Google Workspace Type |
|-----------|-----------------------|
| `application/vnd.google-apps.document` | Google Docs |
| `application/vnd.google-apps.spreadsheet` | Google Sheets |
| `application/vnd.google-apps.presentation` | Google Slides |
| `application/vnd.google-apps.folder` | Folder |
| `application/vnd.google-apps.drawing` | Google Drawing |

For v1 of this plugin, we focus exclusively on **Google Docs** (`application/vnd.google-apps.document`). Other types could be added later.

## Error Codes

| HTTP Code | Meaning | Our Response |
|-----------|---------|--------------|
| 401 | Invalid credentials | Mark plugin unavailable |
| 403 | Insufficient permissions | Mark plugin unavailable, log which permission is missing |
| 404 | File/folder not found | Mark plugin unavailable (folder ID wrong) |
| 429 | Rate limit exceeded | Exponential backoff + retry (max 3) |
| 500 | Google server error | Retry once, then skip |
| 503 | Service unavailable | Retry once, then skip |

## Dependencies to Add

```toml
# In pyproject.toml [project.dependencies]
"google-api-python-client>=2.100.0",
"google-auth>=2.23.0",
```

Optional (if HTML fallback is needed):
```toml
"markdownify>=0.13.0",
```
