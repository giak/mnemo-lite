# EPIC-16: TypeScript LSP Integration

**Status**: 📝 **READY FOR IMPLEMENTATION** (0/18 pts complete)
**Priority**: P1 (High - Enhances TypeScript type intelligence)
**Epic Points**: 18 pts (0 pts completed, 18 pts remaining)
**Timeline**: Week 10-11 (Phase 3)
**Depends On**: EPIC-15 (TypeScript/JavaScript parsers must be complete)
**Related**: EPIC-13 (Python LSP Integration - reference implementation)
**Last Updated**: 2025-10-23 (EPIC-16 Created - Post EPIC-15 completion)

---

## 🎯 Epic Goal

Enhance TypeScript/JavaScript type intelligence by integrating **tsserver** (TypeScript Language Server), improving type extraction accuracy from **70% (heuristic) → 95%+ (LSP-powered)**.

This epic transforms MnemoLite's TypeScript support from basic AST parsing to advanced type-aware analysis with:
- ✅ **Type resolution**: Resolve `User` → `{ id: string, name: string }`
- ✅ **Import tracking**: Track where types are imported from
- ✅ **Generic resolution**: Resolve `Promise<T>` → `Promise<User>`
- ✅ **Type inference**: Infer return types from implementations
- ✅ **Error detection**: Detect TypeScript type errors

---

## 📊 Current State (Post EPIC-15)

**Type Extraction**: AST heuristic only

**Example TypeScript**:
```typescript
export interface User {
  id: string;
  name: string;
}

export class UserService {
  async getUser(id: string): Promise<User> {
    return await api.get(`/users/${id}`);
  }
}
```

**Current Metadata** (EPIC-15 - Heuristic):
```json
{
  "name": "getUser",
  "chunk_type": "method",
  "metadata": {
    "signature": "async getUser(id: string): Promise<User>",
    "parameters": ["id"],  // ← Just names
    "return_type": "Promise<User>",  // ← Unresolved string
    "is_async": true
  }
}
```

**Pain Points**:
- ❌ Types are **strings**, not resolved types
- ❌ No import tracking (`User` from where?)
- ❌ No generic resolution (`Promise<User>` → ?)
- ❌ No type inference
- ❌ No error detection

**Accuracy**: ~70% (basic heuristic)

---

## 🚀 Target State (Post EPIC-16)

**Type Extraction**: LSP-powered via tsserver

**Target Metadata** (EPIC-16 - LSP):
```json
{
  "name": "getUser",
  "chunk_type": "method",
  "metadata": {
    "signature": "async getUser(id: string): Promise<User>",
    "parameters": [
      {
        "name": "id",
        "type": "string",
        "type_info": {
          "kind": "string",
          "primitive": true
        }
      }
    ],
    "return_type": {
      "type": "Promise<User>",
      "resolved_type": "Promise<{ id: string; name: string }>",  // ← Resolved!
      "generic_args": ["User"],
      "definition": {
        "file": "types.ts",
        "line": 1,
        "character": 0
      }
    },
    "is_async": true,
    "imports": [
      {
        "symbol": "User",
        "from": "./types",
        "resolved_path": "/project/types.ts"
      }
    ],
    "type_errors": [],
    "inferred_types": {
      "return_statement": "Promise<User>"
    }
  }
}
```

**Benefits**:
- ✅ Types **resolved** to structures
- ✅ Imports **tracked** with file locations
- ✅ Generics **resolved** (Promise<T> → Promise<User>)
- ✅ Type **inference** working
- ✅ Type **errors** detected

**Accuracy**: ~95%+ (LSP-powered, similar to Pyright for Python)

---

## 📝 Stories Breakdown

### **Story 16.1: TypeScript LSP Client** (8 pts) 📝 READY

**Status**: 📝 **READY FOR IMPLEMENTATION**
**Analysis**: [EPIC-16_STORY_16.1_ANALYSIS.md](EPIC-16_STORY_16.1_ANALYSIS.md)
**User Story**: As a code indexer, I want a TypeScript Language Server client so that I can query type information from tsserver.

**Acceptance Criteria** (0/8):
- [ ] Node.js + TypeScript installed in Docker image
- [ ] `TypeScriptLSPClient` class created
- [ ] LSP protocol communication (JSON-RPC over stdio)
- [ ] `start()` launches tsserver subprocess
- [ ] `stop()` stops tsserver gracefully
- [ ] `get_hover()` retrieves type info at position
- [ ] `get_definition()` retrieves definition location
- [ ] Circuit breaker for error handling
- [ ] Unit tests: 10+ test cases

**Implementation**: Create LSP client similar to PyrightLSPClient (EPIC-13), communicate with tsserver via stdio.

**Key Files**:
- `api/services/typescript_lsp_client.py` (new, ~250 lines)
- `tests/services/test_typescript_lsp_client.py` (new, ~150 lines)
- `db/Dockerfile` or `api/Dockerfile` (Node.js installation)

---

### **Story 16.2: TypeExtractorService Extension** (5 pts) 📝 READY

**Status**: 📝 **READY FOR IMPLEMENTATION**
**Analysis**: [EPIC-16_STORY_16.2_ANALYSIS.md](EPIC-16_STORY_16.2_ANALYSIS.md)
**User Story**: As a type extractor, I want to use TypeScript LSP for type resolution so that TypeScript metadata is 95%+ accurate.

**Acceptance Criteria** (0/7):
- [ ] Add `typescript_lsp` parameter to TypeExtractorService
- [ ] Implement `_extract_typescript_types()` method
- [ ] Parse LSP hover responses → structured metadata
- [ ] Extract parameter types with type info
- [ ] Extract return types with resolution
- [ ] Resolve generic types (e.g., Promise<T>)
- [ ] Track imports (symbol → file location)
- [ ] Cache LSP responses in Redis
- [ ] Integration tests: 5+ test cases

**Implementation**: Extend existing TypeExtractorService (EPIC-13) to support TypeScript via tsserver.

**Key Files**:
- `api/services/type_extractor_service.py` (modify, +120 lines)
- `tests/services/test_type_extractor_service.py` (modify, +100 lines)

---

### **Story 16.3: Integration & Performance** (3 pts) 📝 READY

**Status**: 📝 **READY FOR IMPLEMENTATION**
**Analysis**: [EPIC-16_STORY_16.3_ANALYSIS.md](EPIC-16_STORY_16.3_ANALYSIS.md)
**User Story**: As a system integrator, I want TypeScript LSP integrated into the indexing pipeline so that type metadata is automatically extracted.

**Acceptance Criteria** (0/5):
- [ ] Initialize TypeScriptLSPClient in app startup
- [ ] Pass typescript_lsp to TypeExtractorService (DI)
- [ ] Graceful degradation if LSP fails (fallback to heuristic)
- [ ] Performance: <10s per file (with LSP)
- [ ] Circuit breaker metrics exposed
- [ ] Integration tests: 3+ scenarios (success, timeout, failure)

**Implementation**: Integrate TypeScript LSP into main.py startup and code indexing pipeline.

**Key Files**:
- `api/main.py` (modify, +30 lines)
- `api/dependencies.py` (modify, +20 lines)
- `tests/integration/test_typescript_lsp_integration.py` (new, ~80 lines)

---

### **Story 16.4: Documentation & Testing** (2 pts) 📝 READY

**Status**: 📝 **READY FOR IMPLEMENTATION**
**Analysis**: [EPIC-16_STORY_16.4_ANALYSIS.md](EPIC-16_STORY_16.4_ANALYSIS.md)
**User Story**: As a developer, I want updated documentation for TypeScript LSP so that I understand how to use and configure it.

**Acceptance Criteria** (0/4):
- [ ] Update CLAUDE.md with TypeScript LSP section
- [ ] Create migration guide (EPIC-15 → EPIC-16)
- [ ] Add TypeScript LSP examples to API docs
- [ ] Update README with type accuracy improvements

**Implementation**: Document TypeScript LSP integration and configuration.

**Key Files**:
- `CLAUDE.md` (modify, §CODE.INTEL section)
- `docs/migration/EPIC-16_MIGRATION_GUIDE.md` (new)
- `docs/api_spec.md` (modify, add TypeScript examples)
- `README.md` (modify, update language support matrix)

---

## 🔍 Technical Analysis

### TypeScript Language Server (tsserver)

**What is tsserver?**
- Official TypeScript compiler API
- Used by VS Code, WebStorm, Sublime Text, etc.
- Provides type checking, auto-completion, go-to-definition, etc.
- Communicates via LSP (Language Server Protocol)

**Installation**:
```bash
npm install -g typescript typescript-language-server
```

**Size**: ~50 MB (Node.js + TypeScript)

**LSP Protocol Example**:
```json
// Request: textDocument/hover
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "textDocument/hover",
  "params": {
    "textDocument": { "uri": "file:///project/test.ts" },
    "position": { "line": 5, "character": 10 }
  }
}

// Response
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "contents": {
      "kind": "markdown",
      "value": "```typescript\n(method) UserService.getUser(id: string): Promise<User>\n```"
    }
  }
}
```

### Architecture

**Components**:
1. **TypeScriptLSPClient** (new)
   - Launches tsserver subprocess
   - Communicates via stdio (LSP protocol)
   - Manages lifecycle (start/stop/restart)
   - Circuit breaker for errors

2. **TypeExtractorService** (extend)
   - Add typescript_lsp parameter
   - Implement `_extract_typescript_types()`
   - Parse LSP responses
   - Cache in Redis

3. **Integration** (main.py, dependencies.py)
   - Initialize TypeScriptLSPClient at startup
   - Inject into TypeExtractorService
   - Graceful degradation on failure

**Flow**:
```
Indexing Pipeline
  ├─ Parse TypeScript file (tree-sitter) [EPIC-15]
  ├─ Extract chunks (functions, classes, interfaces) [EPIC-15]
  ├─ Extract metadata (TypeExtractorService)
  │   ├─ Create temporary workspace
  │   ├─ Call TypeScriptLSPClient.get_hover() [EPIC-16]
  │   ├─ Parse LSP response
  │   └─ Return structured metadata
  └─ Store chunks with metadata
```

---

## 📊 Impact Analysis

### Before EPIC-16 (EPIC-15 only)

| Feature | Python | TypeScript | JavaScript |
|---------|--------|------------|------------|
| **AST Parsing** | ✅ | ✅ | ✅ |
| **Semantic Chunking** | ✅ | ✅ | ✅ |
| **LSP Integration** | ✅ Pyright | ❌ None | ❌ None |
| **Type Accuracy** | 95%+ | 70% | 70% |
| **Type Resolution** | ✅ | ❌ | ❌ |
| **Import Tracking** | ✅ | ❌ | ❌ |
| **Error Detection** | ✅ | ❌ | ❌ |

**TypeScript Example** (Before):
```json
{
  "return_type": "Promise<User>",  // ← String, not resolved
  "parameters": ["id"]  // ← Just names
}
```

### After EPIC-16

| Feature | Python | TypeScript | JavaScript |
|---------|--------|------------|------------|
| **AST Parsing** | ✅ | ✅ | ✅ |
| **Semantic Chunking** | ✅ | ✅ | ✅ |
| **LSP Integration** | ✅ Pyright | ✅ tsserver | ✅ tsserver |
| **Type Accuracy** | 95%+ | 95%+ | 90%+ |
| **Type Resolution** | ✅ | ✅ | ✅ |
| **Import Tracking** | ✅ | ✅ | ✅ |
| **Error Detection** | ✅ | ✅ | ✅ |

**TypeScript Example** (After):
```json
{
  "return_type": {
    "type": "Promise<User>",
    "resolved_type": "Promise<{ id: string; name: string }>",  // ← Resolved!
    "definition": { "file": "types.ts", "line": 1 }
  },
  "parameters": [
    {
      "name": "id",
      "type": "string",
      "type_info": { "kind": "string", "primitive": true }
    }
  ]
}
```

**Improvement**: 70% → 95%+ type accuracy (+35% improvement)

---

## 📈 Success Metrics

### Technical Metrics
- ✅ Type accuracy: 70% → 95%+ (+35% improvement)
- ✅ Types resolved: 0% → 80%+ (e.g., User → { id: string })
- ✅ Imports tracked: 0% → 90%+ (symbol → file location)
- ✅ Generics resolved: 0% → 85%+ (Promise<T> → Promise<User>)
- ✅ Performance: <10s per file (acceptable with caching)
- ✅ Zero regressions: Python + basic TypeScript unchanged

### Business Metrics
- ✅ TypeScript type intelligence: Same quality as Python (Pyright)
- ✅ Developer experience: Go-to-definition, type info on hover
- ✅ Error detection: Catch type errors during indexing

### Quality Metrics
- ✅ Test coverage: >90% for TypeScript LSP client
- ✅ Documentation: Complete migration guide
- ✅ Stability: Circuit breaker prevents cascading failures

---

## 🚦 Risks & Mitigation

### Risk 1: tsserver Performance Impact
**Probability**: Medium
**Impact**: High
**Mitigation**:
- Timeout protection (5s max per file)
- Fallback to heuristic on timeout
- Redis caching (TTL: 1h)
- Optional (env var `TYPESCRIPT_LSP_ENABLED=false`)

### Risk 2: Docker Image Size Increase
**Probability**: High
**Impact**: Low
**Mitigation**:
- Multi-stage build (Node.js slim)
- Size increase: +80 MB (acceptable)
- Optional LSP (can disable)

### Risk 3: Workspace Management Complexity
**Probability**: Medium
**Impact**: Medium
**Mitigation**:
- Temporary workspace per repository
- Minimal tsconfig.json generated
- Works without node_modules (basic mode)

### Risk 4: Circuit Breaker False Positives
**Probability**: Low
**Impact**: Medium
**Mitigation**:
- Threshold: 3 failures before open
- Recovery timeout: 60s
- Metrics exposed for monitoring

---

## 🔗 Related Documents

### EPIC-15 (Prerequisite)
- [EPIC-15_TYPESCRIPT_JAVASCRIPT_SUPPORT.md](EPIC-15_TYPESCRIPT_JAVASCRIPT_SUPPORT.md) - TypeScript parsers must be implemented first

### EPIC-13 (Reference Implementation)
- [EPIC-13_LSP_INTEGRATION.md](EPIC-13_LSP_INTEGRATION.md) - Python LSP (Pyright) implementation
- [EPIC-13_STORY_13.1_COMPLETION_REPORT.md](EPIC-13_STORY_13.1_COMPLETION_REPORT.md) - Pyright LSP client reference

### Story Analysis Documents
- [EPIC-16_STORY_16.1_ANALYSIS.md](EPIC-16_STORY_16.1_ANALYSIS.md) - TypeScript LSP Client
- [EPIC-16_STORY_16.2_ANALYSIS.md](EPIC-16_STORY_16.2_ANALYSIS.md) - TypeExtractor extension
- [EPIC-16_STORY_16.3_ANALYSIS.md](EPIC-16_STORY_16.3_ANALYSIS.md) - Integration & Performance
- [EPIC-16_STORY_16.4_ANALYSIS.md](EPIC-16_STORY_16.4_ANALYSIS.md) - Documentation & Testing

---

## 📅 Timeline

**Week 10** (Story 16.1-16.2):
- Day 1-2: Story 16.1 - TypeScript LSP Client setup (Docker, Node.js)
- Day 3-4: Story 16.1 - LSP protocol implementation
- Day 5: Story 16.2 - TypeExtractorService extension (start)

**Week 11** (Story 16.2-16.4):
- Day 1-2: Story 16.2 - TypeExtractorService extension (complete)
- Day 3: Story 16.3 - Integration & Performance
- Day 4: Story 16.4 - Documentation
- Day 5: Testing & validation

**Total Duration**: 2 weeks (10 working days)

---

## ✅ Definition of Done

**EPIC-16 is complete when**:
1. ✅ All 4 stories (16.1-16.4) marked as COMPLETE
2. ✅ All 18 story points delivered
3. ✅ All acceptance criteria met (100%)
4. ✅ TypeScript type accuracy: 95%+ (validated with tests)
5. ✅ Performance benchmarks met (<10s per file)
6. ✅ Documentation updated (CLAUDE.md, migration guide, API docs)
7. ✅ Zero regressions (Python + basic TypeScript unchanged)
8. ✅ EPIC-16 COMPLETION REPORT published

---

**Last Updated**: 2025-10-23
**Next Action**: Review and approve EPIC-16, then start Story 16.1 implementation
