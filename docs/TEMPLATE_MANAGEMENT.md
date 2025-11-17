# Template Management Guide

## Overview

The NDA Tool supports template versioning, allowing you to:
- Create new templates
- Create new versions of existing templates
- Track which template version was used for each NDA
- Set the default/current version
- View version history

## How Template Versioning Works

### Template Key

Each template has a unique `template_key` (e.g., `standard-mutual-nda`). This key groups all versions of the same template together.

### Version Numbers

Versions are automatically incremented:
- First upload with a `template_key` → Version 1
- Second upload with the same `template_key` → Version 2
- And so on...

### Current Version

Only one version per `template_key` can be marked as "current". This is the version that will be used by default when creating NDAs.

## Managing Templates via UI

### Access Template Management

1. Navigate to **Admin** → **Template Management** tab
2. You must be logged in as an admin user

### Creating a New Template

1. Click **"+ Create Template"**
2. Fill in the form:
   - **Template Name**: Display name (e.g., "Standard Mutual NDA")
   - **Template Key**: Unique identifier (e.g., `standard-mutual-nda`)
     - Auto-generated from name if left empty
     - Use the same key to create new versions
   - **Description**: Optional description
   - **Change Notes**: Optional notes about changes (for new versions)
   - **Template File**: Upload a `.docx` file
3. Click **"Create Template"**

### Creating a New Version

**Method 1: Using the UI (Recommended)**

1. Find the template you want to version in the Template Management list
2. Click the **"New Version"** button on that template
3. The form will be pre-filled with:
   - Template Name (locked)
   - Template Key (locked - same as original)
4. Upload the updated `.docx` file
5. Add **Change Notes** describing what changed (recommended)
6. Click **"Create Version X"** (where X is the next version number)
7. The system will automatically:
   - Increment the version number
   - Mark the new version as current
   - Mark previous versions as not current

**Method 2: Using the Create Template Form**

1. Click **"+ Create Template"**
2. Use the **same Template Key** as the existing template
3. Upload the updated `.docx` file
4. Optionally add **Change Notes** describing what changed
5. The system will automatically create a new version

### Viewing Version History

1. Click **"View Versions"** on any template
2. See all versions with:
   - Version number
   - Current status badge
   - Change notes
   - Creation date and creator

### Setting Current Version

1. Open version history for a template
2. Click **"Set as Current"** on any version
3. That version becomes the default for new NDAs

### Archiving Templates

Templates can be archived to hide them from normal use without deleting them:

1. Find the template in the Template Management list
2. Click the **"Archive"** button (yellow button)
3. The template will be marked as inactive and hidden from normal listings
4. To view archived templates, check the **"Show archived"** checkbox
5. To unarchive, click **"Unarchive"** on an archived template

**Note:** Archived templates:
- Are not shown in the template dropdown when creating NDAs
- Can still be viewed in version history
- Can be restored by unarchiving
- Preserve all version history

## Managing Templates via API

### Create Template

```bash
curl -X POST "http://localhost:8000/templates" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "name=Standard Mutual NDA" \
  -F "template_key=standard-mutual-nda" \
  -F "description=Standard mutual NDA template" \
  -F "file=@template.docx"
```

### Create New Version

```bash
curl -X POST "http://localhost:8000/templates" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "name=Standard Mutual NDA" \
  -F "template_key=standard-mutual-nda" \
  -F "change_notes=Updated confidentiality clause" \
  -F "file=@template_v2.docx"
```

### List Templates

```bash
# List current versions only
curl "http://localhost:8000/templates?active_only=true&current_only=true" \
  -H "Authorization: Bearer YOUR_TOKEN"

# List all versions
curl "http://localhost:8000/templates?active_only=true&current_only=false" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### List Versions of a Template

```bash
curl "http://localhost:8000/templates/standard-mutual-nda/versions" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Set Current Version

```bash
curl -X POST "http://localhost:8000/templates/standard-mutual-nda/versions/2/set-current" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Template Variables

Templates can contain placeholders that are replaced when creating NDAs:

- `{{counterparty_name}}` - Name of the counterparty
- `{{disclosing_party}}` - Name of the disclosing party
- `{{receiving_party}}` - Name of the receiving party
- `{{effective_date}}` - Effective date (formatted)
- `{{term_months}}` - Term in months
- `{{survival_months}}` - Survival period in months
- `{{governing_law}}` - Governing law/jurisdiction

## Best Practices

1. **Use Descriptive Template Keys**: Use clear, consistent naming (e.g., `standard-mutual-nda`, `unilateral-nda`)

2. **Document Changes**: Always fill in "Change Notes" when creating new versions to track what changed

3. **Test Before Making Current**: Test new versions before setting them as current

4. **Version Control**: Keep track of template versions outside the system (e.g., Git) for backup

5. **Template Naming**: Use consistent naming conventions for template names

## Tracking Template Usage

When an NDA is created from a template, the system tracks:
- `template_id`: The specific template version used
- `template_version`: The version number
- This information is stored in the `nda_records` table

You can query NDAs by template version to see which version was used for each NDA.

