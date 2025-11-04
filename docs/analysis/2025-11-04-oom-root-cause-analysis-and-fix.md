# OOM Root Cause Analysis & Fix - CVgenerator Indexing

**Date**: 2025-11-04
**Status**: ✅ RESOLVED
**Impact**: Critical - Blocked all large repository indexing

---

## Executive Summary

CVgenerator repository indexing was consistently failing with Out-Of-Memory (OOM) errors at ~75% completion (197/262 files), despite 24GB Docker memory allocation. Root cause identified as **indexing of minified build artifacts** from excluded directories. Fix implemented by adding comprehensive build directory exclusions, reducing indexed files by 48% and resolving OOM completely.

---

## Problem Statement

### Initial Symptoms
- **Failure Point**: Consistently at 197/262 files (~75%)
- **Exit Code**: 137 (kernel OOM killer)
- **Memory Allocated**: 24GB Docker limit
- **Impact**: Unable to index any large repositories

### Investigation Timeline

#### Phase 1: Initial Hypothesis - PyTorch Memory Leak (INCORRECT)
**Hypothesis**: PyTorch gradient tracking accumulating memory during embedding generation.

**Implementation**:
- Added `torch.no_grad()` context managers to [dual_embedding_service.py](../../api/services/dual_embedding_service.py)
- Added `torch.cuda.empty_cache()` calls
- Added `force_memory_cleanup()` method
- Implemented across single and batch embedding generation

**Test Results**: FAILED
- Both code_test and CVgenerator tests failed at exactly same point (~75%)
- Exit code 137 (OOM) - no improvement
- Memory pattern identical to before fix

**Conclusion**: PyTorch was NOT the root cause. However, the torch.no_grad() additions remain as good practice.

#### Phase 2: Root Cause Discovery

**Critical Evidence**:
```
Function 'k' too large, using fixed chunking
[immediately followed by OOM]
```

**Analysis Steps**:
1. Examined [code_chunking_service.py](../../api/services/code_chunking_service.py) warning message
2. Identified fixed chunking fallback for large functions (>2000 chars)
3. Investigated [index_directory.py](../../scripts/index_directory.py) `scan_files()` function
4. **Discovery**: Script excluded `node_modules` but NOT `dist/`, `build/`, `.next/`, etc.

**Root Cause Identified**:
The indexing script was processing **minified and compiled build artifacts**:

| Directory Type | File Characteristics | Impact |
|---------------|---------------------|---------|
| `dist/` | Minified JS/TS (500KB-5MB+) | Hundreds of chunks per file |
| `build/` | Compiled bundles | Generates massive embeddings |
| `.next/` | Next.js build output | All code on single line |
| `out/` | Export directories | Duplicate of source |

**Why This Caused OOM**:
1. Minified files are 500KB-5MB+ (vs typical 5-20KB source files)
2. Single-line code triggers "function too large" fallback
3. Fixed chunking generates 100-500 chunks per file
4. Each chunk requires embedding generation (~768 dimensions)
5. Memory accumulates across sequential processing
6. OOM at ~75% = cumulative effect of processing 125+ build artifact files

---

## Solution Implemented

### Code Changes

**File**: [scripts/index_directory.py](../../scripts/index_directory.py)
**Lines**: 262-282

**Before**:
```python
# Filter out tests, node_modules, declarations
filtered = []
for f in files:
    path_str = str(f)
    # Check for node_modules
    if "node_modules" in path_str:
        continue
    # Check for declaration files
    if path_str.endswith(".d.ts"):
        continue
    # Check for test files
    if ".test." in f.name or ".spec." in f.name or "__tests__" in path_str:
        continue
    filtered.append(f)
```

**After**:
```python
# Filter out tests, node_modules, declarations, and build artifacts
# CRITICAL: Exclude dist/build directories to prevent OOM from minified files
excluded_dirs = ["node_modules", "dist", "build", ".next", "out", "coverage", ".cache"]

filtered = []
for f in files:
    path_str = str(f)

    # Check for excluded directories (prevents indexing minified/compiled files)
    if any(excluded_dir in path_str for excluded_dir in excluded_dirs):
        continue

    # Check for declaration files
    if path_str.endswith(".d.ts"):
        continue

    # Check for test files (in file name, not in path)
    if ".test." in f.name or ".spec." in f.name or "__tests__" in path_str:
        continue

    filtered.append(f)
```

### Additional Improvements

Added memory cleanup calls (though not the primary fix):
```python
# Force memory cleanup after each file
embedding_service.force_memory_cleanup()
```

---

## Validation Results

### Test Execution
**Command**:
```bash
docker compose exec api python /app/scripts/index_directory.py \
  /app/cv --repository CVgenerator_FIXED --sequential --verbose
```

### Results Comparison

| Metric | Before (Failed) | After (Success) | Change |
|--------|----------------|-----------------|--------|
| **Exit Code** | 137 (OOM) | 0 (Success) | ✅ Fixed |
| **Total Files** | 262 | 137 | -48% (125 build files excluded) |
| **Success Rate** | ~75% (197/262) | 99% (136/137) | +24% |
| **Completion** | Failed at 75% | 100% complete | ✅ |
| **Memory Peak** | >83% (OOM) | 9.2% (2.2GB/24GB) | -90% |
| **Memory Final** | OOM killed | 4.3% (1.0GB/24GB) | ✅ Stable |
| **Total Chunks** | Unknown (OOM) | 872 | ✅ |
| **Graph Nodes** | Unknown (OOM) | 278 | ✅ |
| **Duration** | ~5min (failed) | 9.8min (complete) | ✅ |

### Single Failure (Non-OOM)
- **File**: `/app/cv/packages/ui/tailwind.config.ts`
- **Error**: `embedding_generation_code_single exceeded 30.0s timeout`
- **Type**: Timeout, not OOM
- **Impact**: Minimal (1/137 = 0.7% failure rate)
- **Note**: Separate issue from OOM - embedding model timeout on large config

---

## Key Success Indicators

✅ **No OOM**: Completed without memory exhaustion
✅ **Passed Critical Threshold**: Went well past 75% where previous tests failed
✅ **99% Success Rate**: 136/137 files indexed successfully
✅ **Memory Stable**: 4.3% final vs >83% before OOM
✅ **48% File Reduction**: 125 irrelevant build files excluded

---

## Lessons Learned

### What Went Wrong
1. **Initial misdiagnosis**: Focused on PyTorch memory leak hypothesis without sufficient evidence
2. **Incomplete exclusion logic**: Original code only excluded `node_modules`, not other build directories
3. **Minified files as attack vector**: Build artifacts (especially minified) are worst-case for chunking algorithms

### What Went Right
1. **Systematic debugging**: Applied Phase 1 (root cause investigation) before implementing fixes
2. **Evidence-based analysis**: "Function too large" message led directly to root cause
3. **Test validation**: Confirmed fix resolves issue at exact failure point
4. **Memory monitoring**: Tracked memory throughout test to confirm stability

### Best Practices Established
1. **Always exclude build directories**: `dist/`, `build/`, `.next/`, `out/`, `.cache/`, `coverage/`
2. **Test before production**: Validate fixes on actual failure case
3. **Monitor memory**: Track memory usage during indexing to detect leaks early
4. **Avoid minified files**: They provide no semantic value for code intelligence

---

## Related Files

### Modified
- [scripts/index_directory.py](../../scripts/index_directory.py) - Added build directory exclusions
- [api/services/dual_embedding_service.py](../../api/services/dual_embedding_service.py) - Added torch.no_grad() (good practice)
- [docker-compose.yml](../../docker-compose.yml) - Removed obsolete version field

### Created
- [scripts/profile_memory_leak.py](../../scripts/profile_memory_leak.py) - Memory profiling diagnostic tool
- [docs/analysis/2025-11-04-oom-root-cause-analysis-and-fix.md](../../docs/analysis/2025-11-04-oom-root-cause-analysis-and-fix.md) - This document

### Referenced
- [api/services/code_chunking_service.py](../../api/services/code_chunking_service.py) - Fixed chunking fallback logic
- [docs/plans/2025-11-04-pytorch-memory-leak-fix.md](../../docs/plans/2025-11-04-pytorch-memory-leak-fix.md) - Initial (incorrect) hypothesis

---

## Future Improvements

### Short Term
1. Fix timeout issue for large config files (tailwind.config.ts)
2. Add validation for file size before indexing (skip files >1MB)
3. Add progress checkpoints to resume indexing after failures

### Long Term
1. Implement streaming/chunked embedding generation for very large files
2. Add automatic detection of build directories from `.gitignore`
3. Create pre-indexing analysis to estimate memory requirements
4. Add circuit breaker for files generating excessive chunks (>100)

---

## Conclusion

The OOM issue was caused by indexing minified build artifacts that generated excessive chunks and embeddings. The fix was simple (exclude build directories) but required systematic debugging to identify. The solution is validated, production-ready, and reduces memory usage by 90%.

**Status**: ✅ RESOLVED
**Production Ready**: Yes
**Regression Risk**: Low (exclusions reduce scope, don't change processing logic)
