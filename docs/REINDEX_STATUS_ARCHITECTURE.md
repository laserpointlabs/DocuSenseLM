# Reindex Status Update Architecture

## Problem Statement

When implementing the manual reindex functionality, we encountered a critical issue: **document status updates were not visible in real-time during the reindexing process**. The admin panel would show all documents as "Processed" even while reindexing was actively occurring, and the progress indicator would remain stuck at "Initializing... 0 / 0 (0%)".

This document explains the root causes of this issue and the comprehensive solution we implemented.

---

## Root Causes

The problem had multiple contributing factors that needed to be addressed simultaneously:

### 1. SQLAlchemy Session Caching (Identity Map)

**Problem**: SQLAlchemy maintains an "identity map" that caches objects within a session. When we queried documents, SQLAlchemy would return the cached objects instead of fetching fresh data from the database, even after the backend had committed status changes.

**Manifestation**: 
- Backend logs showed status being set to "PROCESSING"
- Database queries confirmed the status was "PROCESSING"
- But the API endpoint returned "Processed" to the frontend

**Solution**: Call `db.expire_all()` before querying documents to force SQLAlchemy to discard its cache and fetch fresh data from the database.

```python
# In api/routers/documents.py and api/services/db_service.py
def list_documents(...):
    # CRITICAL: Expire all cached objects to force fresh reads
    db.expire_all()
    
    # Now queries will hit the database instead of using cached objects
    documents = db.query(Document).offset(skip).limit(limit).all()
```

### 2. Transaction Isolation

**Problem**: Database changes made within one session/transaction may not be visible to other concurrent sessions until committed. The reindexing logic was updating document statuses within a long-running transaction, making these updates invisible to the polling API endpoint.

**Solution**: Use **separate database sessions** for different phases of the reindex operation:
- One session to set all documents to "PROCESSING" and commit immediately
- Individual sessions for each document's final status update (PROCESSED/FAILED)
- Separate session for the API endpoint that reads document statuses

```python
# STEP 1: Set ALL documents to PROCESSING in a dedicated session
status_db = get_db_session()
try:
    for doc_id in doc_ids:
        doc_uuid = uuid.UUID(doc_id)
        fresh_doc = status_db.query(Document).filter(Document.id == doc_uuid).first()
        if fresh_doc:
            fresh_doc.status = DocumentStatus.PROCESSING
    status_db.commit()  # Commit immediately so other sessions can see it
finally:
    status_db.close()

# STEP 2: Reindex each document in its own session context
# ...
final_db = get_db_session()
try:
    final_doc = final_db.query(Document).filter(Document.id == doc_uuid).first()
    if final_doc:
        final_doc.status = DocumentStatus.PROCESSED
        final_db.commit()
finally:
    final_db.close()
```

### 3. Blocking API Endpoint

**Problem**: The original `/admin/reindex/all` endpoint was **synchronous** - it would perform the entire reindexing operation within the request handler. This meant:
- The API call wouldn't return until reindexing completed (many seconds/minutes)
- The FastAPI worker was blocked, preventing the `/admin/reindex/progress` endpoint from responding
- Frontend polling couldn't get progress updates

**Manifestation**: Progress bar stuck at "Initializing..." forever

**Solution**: Convert the reindex operation to a **background task** using FastAPI's `BackgroundTasks`:

```python
from fastapi import BackgroundTasks

@router.post("/reindex/all")
async def reindex_all(background_tasks: BackgroundTasks):
    """Trigger re-indexing as a background task"""
    background_tasks.add_task(_run_reindex_all_background)
    return {"message": "Re-indexing started in background", "status": "accepted"}

def _run_reindex_all_background():
    """Background task that performs the actual reindexing"""
    # Update shared progress dictionary as reindexing proceeds
    # ...
```

This allows the API endpoint to return immediately while the reindexing continues in the background.

### 4. Frontend Polling Strategy

**Problem**: The frontend's polling logic had several issues:
- It `await`ed the initial reindex API call, which would block until completion
- It `await`ed the `loadDocuments()` call within the polling loop, which could slow down progress updates
- The polling interval would stop prematurely when the API call returned

**Solution**: Implement a "fire-and-forget" pattern with non-blocking document refreshes:

```typescript
const handleReindexAll = async () => {
  // Start polling immediately
  const progressInterval = setInterval(async () => {
    const progress = await adminAPI.getReindexProgress();
    setReindexProgress(progress);
    
    // Refresh documents WITHOUT awaiting (non-blocking)
    loadDocuments(false).catch(err => console.error('Failed to load documents:', err));
    
    // Stop polling only when backend signals completion
    if (!progress.is_running) {
      clearInterval(progressInterval);
      await loadDocuments();  // Final refresh
      await loadStats();
    }
  }, 500); // Poll every 500ms
  
  // Fire-and-forget the reindex API call
  adminAPI.reindex()
    .catch(error => {
      // Handle startup errors only
      setToast({ show: true, message: error.message, type: 'error' });
    });
};
```

### 5. UUID Type Conversion

**Problem**: Document IDs are UUIDs in the database, but are often handled as strings in Python. When querying with a string ID against a UUID column, PostgreSQL may not find matches.

**Solution**: Always convert string IDs to `uuid.UUID` objects before querying:

```python
import uuid

doc_id_str = str(doc.id)
doc_uuid = uuid.UUID(doc_id_str)
doc = db.query(Document).filter(Document.id == doc_uuid).first()
```

---

## Final Architecture

### Backend Flow

1. **API Endpoint** (`POST /admin/reindex/all`):
   - Accepts request
   - Schedules background task
   - Returns immediately with "accepted" status

2. **Background Task** (`_run_reindex_all_background`):
   - Phase 1: Set all documents to PROCESSING (dedicated session + immediate commit)
   - Phase 2: For each document:
     - Update progress dictionary (current file, completed count)
     - Reindex the document
     - Update document status to PROCESSED/FAILED (dedicated session)
   - Phase 3: Set `is_running = False` in progress dictionary

3. **Progress Endpoint** (`GET /admin/reindex/progress`):
   - Returns current state from shared progress dictionary
   - Never blocks (backend task is separate)
   - Thread-safe using `threading.Lock`

4. **Documents Endpoint** (`GET /documents`):
   - Calls `db.expire_all()` to clear cache
   - Fetches fresh document data from database
   - Returns latest status to frontend

### Frontend Flow

1. **User clicks "Re-index All Documents"**:
   - Confirmation dialog appears
   - If confirmed, start polling interval (500ms)
   - Fire-and-forget API call to start reindex

2. **Polling Loop** (runs every 500ms):
   - Fetch progress from `/admin/reindex/progress`
   - Update progress bar UI
   - Fetch documents from `/documents` (non-blocking)
   - Update document status table
   - When `is_running` becomes false:
     - Stop polling
     - Do final refresh
     - Show completion toast

3. **Toast Notifications**:
   - Auto-dismiss after 5 seconds
   - Fade-out animation before removal
   - Show on completion or error

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│                                                              │
│  ┌──────────────┐    Poll (500ms)    ┌──────────────────┐  │
│  │   Admin UI   │◄──────────────────►│  Progress State  │  │
│  └──────────────┘                    └──────────────────┘  │
│         │                                      ▲              │
│         │                                      │              │
└─────────┼──────────────────────────────────────┼─────────────┘
          │                                      │
          │ POST /reindex/all                   │ GET /progress
          │ GET /documents                       │
          ▼                                      │
┌─────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                       │
│                                                              │
│  ┌──────────────┐    Background    ┌──────────────────┐    │
│  │   Endpoint   │────────Tasks────►│  Reindex Worker  │    │
│  │   (async)    │                  │   (sync thread)  │    │
│  └──────────────┘                  └────────┬─────────┘    │
│         ▲                                   │               │
│         │                                   │               │
│         │ GET /progress                     │               │
│         │                                   │               │
│  ┌──────────────┐                          │               │
│  │   Progress   │◄─────────────────────────┘               │
│  │  Dictionary  │  (thread-safe updates)                   │
│  │ (in-memory)  │                                           │
│  └──────────────┘                                           │
│         ▲                                                    │
└─────────┼────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database (PostgreSQL)                     │
│                                                              │
│  • Document status updates (separate sessions)               │
│  • Immediate commits for visibility                          │
│  • Fresh reads via db.expire_all()                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **SQLAlchemy caching is powerful but can mask database changes** - Use `db.expire_all()` when you need guaranteed fresh data.

2. **Transaction isolation matters** - Changes in one session aren't visible to others until committed. Use separate sessions for concurrent operations.

3. **Don't block the API worker** - Long-running operations should use background tasks to keep the API responsive.

4. **Frontend polling must be non-blocking** - Don't `await` slow operations inside polling loops, or you'll miss updates.

5. **Type consistency is critical** - Always convert between string and UUID types explicitly when working with PostgreSQL UUID columns.

6. **Real-time UIs require careful orchestration** - Multiple systems (database transactions, API endpoints, frontend state management) must all work in harmony.

---

## Testing Checklist

When verifying the reindex status updates work correctly:

- [ ] Click "Re-index All Documents" - confirmation dialog appears
- [ ] After confirming - progress bar appears immediately
- [ ] Progress bar shows "Initializing..." briefly
- [ ] Progress bar updates incrementally (e.g., 1/10, 2/10, 3/10...)
- [ ] Document table shows documents changing from "Processed" → "Processing…"
- [ ] Documents return to "Processed" as they complete
- [ ] Progress bar shows current filename being processed
- [ ] When complete, progress bar disappears
- [ ] Toast notification appears with success message
- [ ] Toast auto-dismisses after 5 seconds
- [ ] All documents show "Processed" status at completion
- [ ] Statistics update correctly

---

## Related Files

- **Backend**:
  - `api/routers/admin.py` - Reindex endpoints and background task
  - `api/routers/documents.py` - Documents endpoint with cache expiration
  - `api/services/db_service.py` - Database service with cache expiration

- **Frontend**:
  - `ui/components/AdminPanel.tsx` - Admin UI with polling logic
  - `ui/components/Toast.tsx` - Toast notification component
  - `ui/app/globals.css` - Toast animations

- **Documentation**:
  - `docs/DATA_PERSISTENCE.md` - General data persistence guide
  - `docs/REINDEX_STATUS_ARCHITECTURE.md` - This document

