# Code Intelligence Gotchas

**Purpose**: Code indexing, embeddings, symbol paths, and graph construction gotchas

**When to reference**: Working with code chunking, embeddings, or dependency graphs

---

## 🟡 CODE-01: Embedding Storage Pattern

**Rule**: Store embeddings in dict BEFORE creating `CodeChunkCreate` model

```python
# ✅ CORRECT
embeddings = {
    "embedding_text": text_vector,
    "embedding_code": code_vector
}
chunk = CodeChunkCreate(
    file_path=path,
    source_code=code,
    **embeddings  # Add embeddings to dict
)

# ❌ WRONG - Cannot assign to Pydantic model after creation
chunk = CodeChunkCreate(file_path=path, source_code=code)
chunk.embedding_text = text_vector  # Pydantic error!
```

**Why**: Pydantic models are immutable after creation

**Detection**: `ValidationError: "CodeChunkCreate" object has no field "embedding_text"`

---

## 🟡 CODE-02: Dual Embedding Domain

**Rule**: Code chunks MUST use `EmbeddingDomain.HYBRID` (not TEXT only)

```python
# ✅ CORRECT
from api.models.embedding import EmbeddingDomain

embeddings = await embedding_service.generate_embeddings(
    texts=[chunk.source_code],
    domain=EmbeddingDomain.HYBRID  # Loads both TEXT + CODE models
)

# ❌ WRONG - Missing code embedding
embeddings = await embedding_service.generate_embeddings(
    texts=[chunk.source_code],
    domain=EmbeddingDomain.TEXT  # Only text model!
)
```

**Why**:
- Code search requires dual embeddings (text + code)
- CODE model: `jina-embeddings-v2-base-code`
- TEXT model: `nomic-embed-text-v1.5`
- RAM usage: ~2.5GB for both models

**Detection**: Code search returns poor results, only text embedding populated

---

## 🟡 CODE-03: Symbol Path Parent Context

**Rule**: `reverse=True` is CRITICAL when extracting parent context

```python
# ✅ CORRECT - Outermost to innermost
parents = extract_parent_context(
    parent_nodes,
    chunk_start=chunk.start_line,
    chunk_end=chunk.end_line,
    reverse=True  # CRITICAL!
)
# Result: ["OuterClass", "MiddleClass", "InnerClass"]

# ❌ WRONG - Innermost to outermost (backwards!)
parents = extract_parent_context(..., reverse=False)
# Result: ["InnerClass", "MiddleClass", "OuterClass"]  # Wrong order!
```

**Why**: Symbol paths are hierarchical, must be outermost-first for correctness

**Example**: `models.user.User.validate` (NOT `validate.User.user.models`)

**Detection**: Symbol search fails, name_path looks backwards

---

## 🟡 CODE-04: Strict Containment Bounds

**Rule**: Use `<` and `>` (strict), NOT `≤` and `≥` for containment checks

```python
# ✅ CORRECT - Strict containment
def is_contained(parent_start, parent_end, chunk_start, chunk_end):
    return parent_start < chunk_start and chunk_end < parent_end

# ❌ WRONG - Boundary false positives
def is_contained(parent_start, parent_end, chunk_start, chunk_end):
    return parent_start <= chunk_start and chunk_end <= parent_end
```

**Why**: Prevents false positives when chunk boundary equals parent boundary

**Example**:
- Parent: lines 10-20
- Chunk: lines 10-15
- With `<=`: FALSE POSITIVE (chunk starts at same line as parent)
- With `<`: CORRECT (chunk must start AFTER parent)

**Detection**: Incorrect parent context, symbol paths include siblings

---

## 🟡 CODE-05: Graph Builtin Filtering

**Rule**: Filter Python builtins when building dependency graph

```python
# ✅ CORRECT
PYTHON_BUILTINS = {"print", "len", "range", "list", "dict", ...}

if target_name not in PYTHON_BUILTINS:
    edges.append(Edge(source=source_id, target=target_id, relation="calls"))

# ❌ WRONG - Graph polluted with builtins
edges.append(Edge(source=source_id, target=target_id, relation="calls"))
# Results in edges to "print", "len", etc. (noise!)
```

**Why**: Builtins are not interesting for dependency analysis, pollute graph

**Detection**: Graph has thousands of edges to "print", "len", etc.

**Builtin lists**: Available in `api/services/graph_construction_service.py`

---

**Total Code Intelligence Gotchas**: 5
