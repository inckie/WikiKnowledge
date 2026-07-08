---
categories:
- knowledge-sources
created: '2026-07-10T05:09:21.070390+00:00'
id: google-docs-extension
modified: '2026-07-10T05:09:21.070412+00:00'
tags:
- google-drive
- apps-script
- extension
- guide
title: Google Docs Extension for WikiKnowledge
type: leaf
---

This guide explains how to create a Google Docs extension (using Google Apps Script) that allows you to view and edit WikiKnowledge tags and categories directly from within Google Docs.

## Setup Guide

**Step 1: Set up the Apps Script Project**
1. Open any Google Doc you want to test with.
2. In the top menu, go to **Extensions > Apps Script**.
3. Rename the project (e.g., "WikiKnowledge Sync").

**Step 2: Enable the Drive Advanced Service**
Standard Apps Script classes (`DriveApp`) cannot read custom file properties. You must enable the advanced API.
1. In the Apps Script editor, look at the left sidebar and click the **"+" (Add a service)** button next to **Services**.
2. Scroll down and select **Drive API**.
3. Leave the version as default (usually v2 or v3) and click **Add**.

**Step 3: Add the Server-Side Code (`Code.gs`)**
Replace the contents of `Code.gs` with the following. This script handles the menu creation, fetching the data, and writing back to Drive while respecting the 124-character limit defined by the WikiKnowledge backend.

```javascript
/**
 * @OnlyCurrentDoc
 */

function onOpen(e) {
  DocumentApp.getUi().createMenu('WikiKnowledge')
      .addItem('Manage Metadata', 'showSidebar')
      .addToUi();
}

function onInstall(e) {
  onOpen(e);
}

function showSidebar() {
  const ui = HtmlService.createHtmlOutputFromFile('Sidebar')
      .setTitle('WikiKnowledge')
      .setWidth(300);
  DocumentApp.getUi().showSidebar(ui);
}

/**
 * Fetches the current document's properties (with fallback to appProperties).
 */
function getWikiKnowledgeData() {
  const docId = DocumentApp.getActiveDocument().getId();
  
  try {
    // Fetch both to support legacy data fallback as done in the python script
    const file = Drive.Files.get(docId, {fields: 'properties,appProperties'});
    
    const props = file.properties || {};
    const appProps = file.appProperties || {};
    
    return {
      tags: props.wk_tags || appProps.wk_tags || '',
      categories: props.wk_categories || appProps.wk_categories || ''
    };
  } catch (e) {
    console.error("Error fetching metadata: ", e);
    return { tags: '', categories: '', error: e.toString() };
  }
}

/**
 * Patches the document's public properties.
 */
function saveWikiKnowledgeData(tags, categories) {
  const docId = DocumentApp.getActiveDocument().getId();
  
  try {
    const resource = {
      properties: {
        wk_tags: tags.substring(0, 124),
        wk_categories: categories.substring(0, 124)
      }
    };
    
    // Changed from .patch() to .update() for Drive API v3 compatibility
    Drive.Files.update(resource, docId);
    return { success: true };
  } catch (e) {
    console.error("Error saving metadata: ", e);
    return { success: false, error: e.toString() };
  }
}
```

**Step 4: Add the Client-Side UI (`Sidebar.html`)**
In the Apps Script editor, click the **"+" icon** next to **Files** and select **HTML**.
Name the file exactly `Sidebar` (it will create `Sidebar.html`).
Paste the following HTML/JS:

```html
<!DOCTYPE html>
<html>
  <head>
    <base target="_top">
    <style>
      body {
        font-family: Arial, sans-serif;
        padding: 15px;
        color: #333;
      }
      .form-group {
        margin-bottom: 20px;
      }
      label {
        display: block;
        font-weight: bold;
        margin-bottom: 5px;
        font-size: 14px;
      }
      input[type="text"] {
        width: 100%;
        padding: 8px;
        box-sizing: border-box;
        border: 1px solid #ccc;
        border-radius: 4px;
      }
      .note {
        font-size: 11px;
        color: #666;
        margin-top: 4px;
      }
      button {
        background-color: #1a73e8;
        color: white;
        border: none;
        padding: 10px 15px;
        border-radius: 4px;
        cursor: pointer;
        width: 100%;
        font-size: 14px;
        font-weight: bold;
      }
      button:hover {
        background-color: #1557b0;
      }
      button:disabled {
        background-color: #a0c2f9;
        cursor: not-allowed;
      }
      #status {
        margin-top: 15px;
        font-size: 13px;
        text-align: center;
      }
      .error { color: #d93025; }
      .success { color: #1e8e3e; }
    </style>
  </head>
  <body>
    
    <div class="form-group">
      <label for="tags">Tags (wk_tags)</label>
      <input type="text" id="tags" placeholder="e.g. guide, python, api">
      <div class="note">Comma-separated. Max 124 chars.</div>
    </div>

    <div class="form-group">
      <label for="categories">Categories (wk_categories)</label>
      <input type="text" id="categories" placeholder="e.g. engineering, docs">
      <div class="note">Comma-separated. Max 124 chars.</div>
    </div>

    <button id="saveBtn" onclick="saveData()">Save Metadata</button>
    <div id="status">Loading data...</div>

    <script>
      window.onload = function() {
        google.script.run
          .withSuccessHandler(populateForm)
          .withFailureHandler(showError)
          .getWikiKnowledgeData();
      };

      function populateForm(data) {
        if (data.error) {
          showError(data.error);
          return;
        }
        document.getElementById('tags').value = data.tags;
        document.getElementById('categories').value = data.categories;
        document.getElementById('status').innerText = "";
      }

      function saveData() {
        const btn = document.getElementById('saveBtn');
        const status = document.getElementById('status');
        
        btn.disabled = true;
        btn.innerText = "Saving...";
        status.innerText = "";
        status.className = "";

        const tags = document.getElementById('tags').value;
        const categories = document.getElementById('categories').value;

        google.script.run
          .withSuccessHandler(function(response) {
            btn.disabled = false;
            btn.innerText = "Save Metadata";
            if (response.success) {
              status.innerText = "Metadata saved successfully!";
              status.className = "success";
            } else {
              showError(response.error);
            }
          })
          .withFailureHandler(function(error) {
            btn.disabled = false;
            btn.innerText = "Save Metadata";
            showError(error);
          })
          .saveWikiKnowledgeData(tags, categories);
      }

      function showError(msg) {
        const status = document.getElementById('status');
        status.innerText = "Error: " + msg;
        status.className = "error";
      }
    </script>
  </body>
</html>
```

**Step 5: Test the Extension**
1. Save the project (disk icon).
2. Go back to your Google Doc and refresh the page.
3. You will now see a new menu item at the top called **WikiKnowledge**.
4. Click **WikiKnowledge > Manage Metadata**.

*Note: The first time you run this, Google will ask for authorization to access your documents and Drive files. Follow the prompts to allow access.*

## Using as a Template

Instead of installing this script manually on every single document you write, you can create a template for all future articles:

1. Create a brand new Google Doc and name it "WikiKnowledge Template".
2. Add the script and HTML files to this document exactly as you did before following the steps above.
3. Save it and bookmark the document.
4. Whenever you need to write a new article for your knowledge base, open this template and click **File > Make a copy**.

The copied document will carry the Apps Script extension with it automatically, and the WikiKnowledge menu will appear perfectly for your new article!