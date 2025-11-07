# RAG Pipeline Audit

Use `scripts/rag_audit.py` to inspect the chunking/index metadata stored in the local database. The report surfaces:

- Document counts by status (processed vs failed).
- Chunk distribution and statistics (min/median/mean/max length, section types).
- Metadata coverage (governing law, mutuality flags).

## Usage

```bash
# Inspect entire corpus and print summary
python scripts/rag_audit.py

# Limit to the first 50 documents and export metrics to JSON
python scripts/rag_audit.py --limit 50 --output /tmp/rag_stats.json
```

The exported JSON is helpful for tracking changes as you tweak chunk sizing, filters, or reranker strategies. Pair this with `eval/compare_rag.py` to evaluate retrieval metrics across configurations.
