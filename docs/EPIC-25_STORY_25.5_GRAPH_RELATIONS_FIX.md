# EPIC-25 Story 25.5: Code Graph Relations Fix

**Date**: 2025-11-01
**Status**: ✅ COMPLETED
**Issue**: Graph had 2,946 nodes but only 11 edges (0.4% ratio) - essentially no relationships

---

## 🔍 Root Cause Analysis

The graph visualization showed nodes but no meaningful connections because:

1. **Python metadata extraction was disabled**
   - `code_chunking_service.py` line 417: Only extracted metadata for TypeScript/JavaScript
   - Python files were chunked but `metadata["calls"]` and `metadata["imports"]` were empty

2. **Wrong AST objects being passed**
   - MetadataExtractorService expects `ast.AST` objects for Python
   - But code_chunking_service was passing `tree_sitter.Node` objects
   - This caused extraction to silently fail with `'tree_sitter.Node' object has no attribute '_fields'`

## ✅ Solutions Implemented

### Fix 1: Enable Python Metadata Extraction

**File**: `/home/giak/Work/MnemoLite/api/services/code_chunking_service.py`
**Line**: 418

**Before**:
```python
if self._metadata_service and language.lower() in ("typescript", "javascript", "tsx"):
    await self._extract_metadata_for_chunks(chunks, tree, source_code, language)
```

**After**:
```python
# EPIC-25 Story 25.5: Enable Python metadata extraction for graph relations
if self._metadata_service and language.lower() in ("python", "typescript", "javascript", "tsx"):
    await self._extract_metadata_for_chunks(chunks, tree, source_code, language)
```

### Fix 2: Parse Python with ast Module

**File**: `/home/giak/Work/MnemoLite/api/services/code_chunking_service.py`
**Lines**: 472-510

**Added Python-specific parsing**:
```python
# EPIC-25: For Python, parse with ast module instead of tree-sitter
if language.lower() == "python":
    import ast as python_ast
    try:
        python_tree = python_ast.parse(source_code)
    except SyntaxError as e:
        logger.warning(f"Failed to parse Python source with ast: {e}")
        for chunk in chunks:
            chunk.metadata = {"imports": [], "calls": []}
        return

# For each chunk, find the corresponding ast node
for chunk in chunks:
    if language.lower() == "python" and python_tree:
        ast_node = None
        for node in python_ast.walk(python_tree):
            if isinstance(node, (python_ast.FunctionDef, python_ast.AsyncFunctionDef, python_ast.ClassDef)):
                if node.name == chunk.name:
                    ast_node = node
                    break

        # Extract metadata using ast objects (not tree-sitter)
        metadata = await self._metadata_service.extract_metadata(
            source_code=source_code,
            node=ast_node,
            tree=python_tree,
            language=language
        )
```

---

## 🧪 Validation

### Test Script: `/home/giak/Work/MnemoLite/api/test_python_metadata.py`

**Test Code**:
```python
def helper_function():
    """A simple helper."""
    return 42

def main_function():
    """Main function that calls helper."""
    result = helper_function()
    print(f"Result: {result}")
    return result
```

**Result**:
```
✅ SUCCESS: Calls extracted for Python!
  Calls: ['helper_function', 'print']
  Imports: []
```

The fix WORKS! Python metadata extraction is now operational.

---

## 📊 Expected Impact

### Before Fix
- **Nodes**: 2,946
- **Edges**: 11 (0.4% ratio)
- **Problem**: Graph showed isolated nodes with no connections

### After Re-indexing (Expected)
- **Nodes**: ~2,000 (CVGenerator)
- **Edges**: ~1,000+ (50%+ ratio)
- **Breakdown**:
  - Function calls: 600-800 edges
  - Imports: 200-300 edges
  - Class inheritance: 50-100 edges

---

## 🚀 Next Steps for User

### Step 1: Re-index CVGenerator Repository

The existing CVGenerator chunks don't have metadata["calls"] because they were created before the fix.

**Option A: Via Web UI** (Recommended)
1. Open http://localhost:8080
2. Navigate to "Upload Code"
3. Select the `/workspace/code_test` directory
4. Repository name: "CVGenerator"
5. Click "Upload and Index"

**Option B: Via API**
```bash
# Use the indexing endpoint with the CVGenerator files
curl -X POST http://localhost:8001/v1/code/index \
  -H "Content-Type: application/json" \
  -d '{ ... }'  # Complex payload, see docs
```

### Step 2: Rebuild Graph

After re-indexing, rebuild the graph:

```bash
curl -X POST http://localhost:8001/v1/code/graph/build \
  -H "Content-Type: application/json" \
  -d '{"repository": "CVGenerator", "language": "python"}'
```

### Step 3: Verify in UI

1. Navigate to the Graph Visualization page
2. Select "CVGenerator" repository
3. Should now see:
   - Nodes with multiple connections
   - Visible arrows between related nodes
   - Interactive hover highlighting working correctly

---

## 📁 Files Modified

1. `/home/giak/Work/MnemoLite/api/services/code_chunking_service.py`
   - Line 418: Added "python" to supported languages
   - Lines 472-541: Added Python ast parsing logic

2. Test Files Created:
   - `/home/giak/Work/MnemoLite/api/test_python_metadata.py` - Validation test
   - `/home/giak/Work/MnemoLite/test_metadata_extraction.py` - Sample code

---

## 🎓 Lessons Learned

### 1. Dual Parser Architecture
- Tree-sitter: Good for chunking (all languages)
- Python ast: Required for metadata extraction (Python-specific)
- TypeScript: Tree-sitter works for both chunking and metadata

### 2. Progressive Disclosure
- The issue appeared simple (add "python" to line 417)
- But deeper investigation revealed AST object mismatch
- Always validate end-to-end, not just surface fixes

### 3. Test-First Debugging
- Created test script BEFORE fixing the real data
- Saved time by catching the ast vs tree-sitter issue early
- Validated solution works before touching production data

---

## ✅ Status Summary

- **Root Cause**: Identified ✅
- **Fix Implemented**: ✅
- **Validation**: ✅ (test script confirms calls extraction works)
- **Production Deployment**: Pending user re-index
- **Graph Visualization**: Will work after re-indexing

**Total Time**: ~2 hours
**Lines of Code Changed**: ~80 lines (mostly additions)
**Risk**: Low (graceful degradation if fails)

---

**Next Session**: User should re-index CVGenerator and verify graph shows connections.
