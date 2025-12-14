# RAG System Troubleshooting Guide

## Case Study: "What do we pay for weeding?" Query Failure

### The Problem

When users asked "What do we pay for weeding?", the system consistently failed to return the correct answer ($55.00 per man hour) from the Franny's Maintenance Agreement, despite the document being processed and indexed.

**Expected Answer:** $55.00 per man, per man hour (plus dumping fees)  
**Actual Answer:** "No specific information on weeding costs" or incorrect references to $15,000 seasonal contract

### Root Cause Analysis

The failure had **two separate causes**:

#### 1. ChromaDB Indexing Bug

The `index_document` function used `collection.count(where={"filename": filename})` to verify chunk counts. However, **ChromaDB's `count()` method does not support the `where` parameter**.

```python
# BROKEN CODE
verify_count = collection.count(where={"filename": filename})  # TypeError!
```

This caused a silent failure during indexing - the document appeared "processed" but chunks were never actually stored in the vector database.

**Fix:**
```python
# WORKING CODE
verify_result = collection.get(where={"filename": filename}, include=[])
verify_count = len(verify_result['ids']) if verify_result and verify_result.get('ids') else 0
```

#### 2. Distance Threshold Too Strict

After fixing the indexing bug, the weeding information was correctly stored in ChromaDB. However, it was still being **excluded during retrieval** because of an overly strict distance threshold.

**The Math:**
- Query: "What do we pay for weeding?"
- Franny chunk (containing "$55/hour weeding"): distance = **0.5924**
- Original threshold: **0.5** (exclude if distance >= 0.5)
- Result: Chunk EXCLUDED ❌

**Fix:** Increased `DISTANCE_THRESHOLD` from 0.5 to **0.75**

```python
# Before
DISTANCE_THRESHOLD = 0.5  # Too strict for OpenAI embeddings

# After  
DISTANCE_THRESHOLD = 0.75  # Allows relevant semantic matches
```

### Why Was the Distance So High?

This is the key insight: **Semantic embeddings don't work like keyword search.**

The Franny document chunk containing weeding information looked like this:
```
--- Page 1 ---
DocuSign Envelope ID: 4D3B88FD-9C62-44F5-A7SB-E6DC33A83E90
Franny's LANDSCAPE CO., INC.
P.O. Box 4847, Framingham, MA 01704
...
WEEDING
Weed out beds, curbs, walkways, etc.
T&M (Time and Material) @ $55.00 per man, per man hour, plus dumping fees.
...
Late Summer/Early Fall Application
Balanced fertilization plus broadleaf weed control
...
```

**The chunk was 273 words total, but only ~20 words were about weeding costs.**

When OpenAI's `text-embedding-3-small` model creates an embedding:
- It represents the **entire chunk's meaning** as a 1536-dimensional vector
- The embedding captures "landscaping maintenance agreement" as the primary concept
- "Weeding costs" is only ~7% of the semantic content
- Result: Distance of 0.59 instead of 0.1

### Comparison: Semantic vs Keyword Search

| Search Type | How It Works | "Weeding" Query Result |
|------------|--------------|------------------------|
| **Keyword (BM25)** | Exact word matching, TF-IDF scoring | Ranks chunk #1 (contains "weeding") |
| **Semantic (Embeddings)** | Meaning-based vector similarity | Distance 0.59 (chunk is about "landscaping" broadly) |

### The Solution: Hybrid Search (IMPLEMENTED)

> ✅ **Hybrid search with RRF is now implemented in `server.py`** (December 2025)

A hybrid search combines both approaches:

1. **Vector Search**: Find semantically similar chunks (understands "cost" ≈ "price" ≈ "rate")
2. **Keyword Search**: Boost chunks containing exact query terms ("weeding")
3. **Score Fusion**: Combine both scores with configurable weights

```
Final Score = (α × semantic_score) + (β × keyword_score)
```

**Benefits of Hybrid Search:**

| Scenario | Pure Semantic | Hybrid |
|----------|--------------|--------|
| "What do we pay for weeding?" | May miss due to dilution | ✅ Keyword boost for "weeding" |
| "landscaping maintenance costs" | ✅ Good semantic match | ✅ Still works |
| "lawn care expenses" | ✅ Understands synonyms | ✅ Semantic handles it |
| "T&M rate for weed removal" | Partial match | ✅ Both contribute |

### Implementation Options for Hybrid Search

#### Option A: Re-rank with Keywords (Simpler - Not Used)
```python
def hybrid_search(query, n_results=10):
    # 1. Get semantic results
    results = collection.query(query_texts=[query], n_results=n_results*2)
    
    # 2. Extract keywords from query
    keywords = extract_keywords(query)  # ["weeding", "pay"]
    
    # 3. Boost scores for keyword matches
    for i, doc in enumerate(results['documents'][0]):
        keyword_hits = sum(1 for kw in keywords if kw.lower() in doc.lower())
        results['distances'][0][i] -= (keyword_hits * 0.1)  # Lower distance = better
    
    # 4. Re-sort and return top n
    return sorted_results[:n_results]
```

#### Option B: Parallel Search with RRF (More Robust - IMPLEMENTED ✅)
```python
def hybrid_search_rrf(query, n_results=10):
    # 1. Semantic search
    semantic_results = collection.query(query_texts=[query], n_results=20)
    
    # 2. Keyword search (BM25 or simple matching)
    keyword_results = keyword_search(query, n_results=20)
    
    # 3. Reciprocal Rank Fusion
    combined_scores = {}
    for rank, doc_id in enumerate(semantic_results):
        combined_scores[doc_id] = combined_scores.get(doc_id, 0) + 1/(60 + rank)
    for rank, doc_id in enumerate(keyword_results):
        combined_scores[doc_id] = combined_scores.get(doc_id, 0) + 1/(60 + rank)
    
    # 4. Return top results by combined score
    return sorted(combined_scores.items(), key=lambda x: -x[1])[:n_results]
```

### Lessons Learned

1. **Test with edge cases**: Always test queries where the answer is a small part of a larger document
2. **Log intermediate steps**: The fix was only possible because we added logging for distance thresholds and inclusion/exclusion decisions
3. **Understand embedding behavior**: Semantic search is powerful but has different failure modes than keyword search
4. **Validate database operations**: Don't assume database operations succeed - verify with explicit checks
5. **Appropriate thresholds**: OpenAI embeddings typically have distances in the 0.3-0.8 range for related content; a 0.5 threshold is too aggressive

### Configuration Reference

Current settings in `server.py`:

```python
# Chunking
chunk_size = 2000        # Characters per chunk
chunk_overlap = 400      # Overlap between chunks

# Retrieval
n_results = 15           # Initial candidates from vector search
DISTANCE_THRESHOLD = 0.75  # Maximum distance to include
max_chunks = 5           # Maximum chunks in final context

# Embedding Model
model = "text-embedding-3-small"  # 1536 dimensions
```

### Testing Commands

Verify the fix works:
```bash
# API test
curl -X POST http://localhost:14242/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What do we pay for weeding?"}'

# Expected response should include "$55.00 per man, per man hour"
```

---

*Document created: December 2025*  
*Related commits: `377c39f` (fix RAG retrieval)*
