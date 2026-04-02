# EPIC-23 MCP Integration - PHASE 2 COMPLÈTE

**Date**: 2025-10-24
**Phase**: 2 - Advanced Features (9 pts → 18 sub-stories)
**Status**: ✅ DÉCOUPAGE COMPLET

---

## 📊 PHASE 2 COMPLÈTE - TOUTES SUB-STORIES

### STORY 23.5: Project Indexing (SUITE - 3 sub-stories restantes)

#### Sub-Story 23.5.2: Reindex File Tool (0.5 pt)

**Objectif**: Tool `reindex_file` pour réindexer fichier unique

**Fichier**: `api/mcp/tools/indexing_tools.py` (ajouter classe)

**Contenu**:
```python
class ReindexFileTool(BaseMCPComponent, MCPWriteOperation):
    """Tool: reindex_file - Reindex single file after modifications."""

    def get_name(self) -> str:
        return "reindex_file"

    def get_description(self) -> str:
        return "Reindex a single file (useful after edits). Updates chunks and embeddings."

    async def execute(
        self,
        file_path: str,
        ctx: Optional[Context] = None
    ) -> IndexResult:
        """Reindex single file."""
        # Validate file exists
        # Call indexing_service.reindex_file()
        # Return IndexResult with single file stats
        pass
```

**Tests**: Test fichier modifié, fichier supprimé, fichier invalide

**Temps estimé**: 1.5h

---

#### Sub-Story 23.5.3: Get Index Status Resource (0.5 pt)

**Objectif**: Resource `project://status` pour statut indexation

**Fichier**: `api/mcp/tools/indexing_tools.py` (ajouter classe)

**Contenu**:
```python
class IndexStatus(MCPBaseResponse):
    """Status of project indexing."""
    status: Literal["not_indexed", "in_progress", "completed", "failed"]
    total_files: int
    total_chunks: int
    languages: List[str]
    last_indexed_at: Optional[datetime]
    embedding_model: str
    cache_stats: dict

class GetIndexStatusResource(BaseMCPComponent, MCPReadOperation):
    """Resource: project://status - Get indexing status."""

    async def get(self, ctx: Optional[Context] = None) -> IndexStatus:
        """Get current indexing status."""
        # Query indexing service for status
        # Return IndexStatus with metadata
        pass
```

**Tests**: Test différents status (not_indexed, in_progress, completed)

**Temps estimé**: 1.5h

---

#### Sub-Story 23.5.4: Indexing Progress Streaming (0.5 pt)

**Objectif**: Real-time progress via ctx.report_progress()

**Fichier**: `api/mcp/tools/indexing_tools.py` (modifier IndexProjectTool)

**Contenu**:
```python
# Dans IndexProjectTool.execute()

async def progress_callback(current: int, total: int, message: str):
    """Report progress in real-time."""
    if ctx:
        progress_pct = (current / total) * 100
        ctx.report_progress(
            progress=current / total,
            message=f"{message} ({current}/{total} files, {progress_pct:.1f}%)"
        )

# Pass callback to indexing service
result = await indexing_service.index_project(
    project_path=str(project_path),
    progress_callback=progress_callback
)
```

**Tests**: Test progress updates (mock ctx.report_progress)

**Temps estimé**: 1.5h

---

### STORY 23.6: Analytics & Observability (2 pts → 4 sub-stories)

#### Sub-Story 23.6.1: Clear Cache Tool (0.5 pt)

**Objectif**: Tool `clear_cache` pour admin cache

**Fichier**: `api/mcp/tools/analytics_tools.py` (nouveau)

**Contenu**:
```python
class ClearCacheTool(BaseMCPComponent, MCPWriteOperation):
    """Tool: clear_cache - Clear cache layers (admin operation)."""

    async def execute(
        self,
        layer: Literal["L1", "L2", "L3", "all"] = "all",
        ctx: Optional[Context] = None
    ) -> MCPBaseResponse:
        """
        Clear cache.

        MCP 2025-06-18: Elicitation for confirmation.
        """
        # Elicit confirmation
        if ctx:
            response = await ctx.elicit(
                prompt=f"Clear {layer} cache? This may impact performance temporarily.",
                schema={"type": "string", "enum": ["yes", "no"]}
            )
            if response.value == "no":
                return MCPBaseResponse(
                    success=False,
                    message="Cache clear cancelled"
                )

        # Clear cache
        cache_service = self.services["cache_service"]
        await cache_service.clear(layer=layer)

        return MCPBaseResponse(
            success=True,
            message=f"Cache {layer} cleared successfully"
        )
```

**Tests**: Test each layer, test elicitation flow

**Temps estimé**: 1.5h

---

#### Sub-Story 23.6.2: Get Cache Stats Resource (0.5 pt)

**Objectif**: Resource `cache://stats` pour stats cache

**Fichier**: `api/mcp/tools/analytics_tools.py` (ajouter classe)

**Contenu**:
```python
class CacheStatsResponse(MCPBaseResponse):
    """Cache statistics."""
    l1_cache: dict  # {hit_rate, size, evictions}
    l2_cache: dict  # Redis stats
    l3_cache: dict  # PostgreSQL stats
    overall_hit_rate: float
    total_requests: int

class GetCacheStatsResource(BaseMCPComponent, MCPReadOperation):
    """Resource: cache://stats - Get cache statistics."""

    async def get(self, ctx: Optional[Context] = None) -> CacheStatsResponse:
        """Get cache stats from all layers."""
        cache_service = self.services["cache_service"]
        stats = await cache_service.get_all_stats()
        return CacheStatsResponse(**stats)
```

**Tests**: Test stats returned, test breakdown par layer

**Temps estimé**: 1.5h

---

#### Sub-Story 23.6.3: Get Search Analytics Resource (0.5 pt)

**Objectif**: Resource `analytics://search` pour analytics recherche

**Fichier**: `api/mcp/tools/analytics_tools.py` (ajouter classe)

**Contenu**:
```python
class SearchAnalyticsResponse(MCPBaseResponse):
    """Search analytics from EPIC-22."""
    period_hours: int
    total_queries: int
    avg_latency_ms: float
    cache_hit_rate: float
    popular_queries: List[dict]  # [{query, count}]
    slow_queries: List[dict]  # [{query, latency_ms}]
    search_modes: dict  # {semantic: N, lexical: M, hybrid: K}

class GetSearchAnalyticsResource(BaseMCPComponent, MCPReadOperation):
    """Resource: analytics://search - Get search performance analytics."""

    async def get(
        self,
        period_hours: int = 24,
        ctx: Optional[Context] = None
    ) -> SearchAnalyticsResponse:
        """
        Get search analytics (EPIC-22 integration).

        Queries metrics_collector from EPIC-22.
        """
        metrics_collector = self.services["metrics_collector"]
        analytics = await metrics_collector.get_search_analytics(period_hours)
        return SearchAnalyticsResponse(**analytics)
```

**Tests**: Test avec different period_hours, test empty results

**Temps estimé**: 2h

---

#### Sub-Story 23.6.4: Real-Time Stats via SSE (0.5 pt)

**Objectif**: Optional SSE streaming pour stats real-time

**Fichier**: `api/mcp/server.py` (ajouter SSE support)

**Contenu**:
```python
# Pour HTTP transport seulement

@server.sse("/analytics/stream")
async def stream_analytics(ctx: Context):
    """
    Server-Sent Events stream for real-time analytics.

    Emits cache stats + search analytics every 5 seconds.
    """
    while True:
        # Get stats
        cache_stats = await get_cache_stats_resource.get()
        search_analytics = await get_search_analytics_resource.get(period_hours=1)

        # Emit SSE event
        yield {
            "event": "analytics_update",
            "data": {
                "cache": cache_stats.model_dump(),
                "search": search_analytics.model_dump(),
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        await asyncio.sleep(5)  # Update every 5s
```

**Tests**: Test SSE connection, test events emitted

**Temps estimé**: 2h

---

### STORY 23.10: Prompts Library (2 pts → 4 sub-stories) ⭐ NOUVEAU

#### Sub-Story 23.10.1: Core Analysis Prompts (0.5 pt)

**Objectif**: 3 prompts de base (analyze, refactor, bugs)

**Fichier**: `api/mcp/tools/prompt_tools.py` (nouveau)

**Contenu**:
```python
"""
Prompt templates for MnemoLite MCP.

Prompts are user-invoked templates that appear in Claude Desktop UI.
"""
from mcp.server.fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register all prompt templates."""

    @mcp.prompt()
    def analyze_codebase(language: str = "all", focus: str = "architecture") -> str:
        """
        Generate prompt to analyze codebase architecture.

        Args:
            language: Language to focus on (all, python, javascript, etc.)
            focus: Analysis focus (architecture, patterns, complexity, etc.)
        """
        return f"""
Analyze the {language} codebase with focus on {focus}.

Please provide:
1. **Architecture Overview**: High-level structure and patterns
2. **Design Patterns**: Identified patterns (MVC, Repository, Factory, etc.)
3. **Code Organization**: Directory structure and modularity
4. **Dependencies**: External libraries and internal coupling
5. **Strengths**: What's well-designed
6. **Improvement Opportunities**: Potential refactoring or redesign

Use code://search to explore the codebase semantically.
Use graph://nodes to understand relationships.
""".strip()

    @mcp.prompt()
    def refactor_suggestions(
        focus: str = "all",
        severity: str = "medium"
    ) -> str:
        """
        Generate prompt to find refactoring opportunities.

        Args:
            focus: Focus area (all, duplication, complexity, naming, etc.)
            severity: Severity level (low, medium, high)
        """
        severity_desc = {
            "low": "minor improvements (style, naming)",
            "medium": "moderate improvements (structure, duplication)",
            "high": "major refactoring (architecture, design patterns)"
        }

        return f"""
Find refactoring opportunities with {severity} severity focus on {focus}.

Criteria:
- **Severity**: {severity_desc.get(severity, "all improvements")}
- **Focus**: {focus}

Please identify:
1. **Code Duplication**: Similar code that could be abstracted
2. **Complexity**: Functions/classes with high cyclomatic complexity
3. **Naming Issues**: Unclear or inconsistent names
4. **Structure**: Opportunities for better organization
5. **Patterns**: Missing or misused design patterns

Use code://similar to detect duplication.
Use graph://callers and graph://callees to understand impact.
Provide specific file:line references.
""".strip()

    @mcp.prompt()
    def find_bugs(severity: str = "high", category: str = "all") -> str:
        """
        Generate prompt to find potential bugs.

        Args:
            severity: Bug severity (high, medium, low)
            category: Bug category (all, logic, security, performance, etc.)
        """
        categories = {
            "all": "all categories",
            "logic": "logic errors (off-by-one, null checks, etc.)",
            "security": "security vulnerabilities (injection, XSS, etc.)",
            "performance": "performance issues (N+1 queries, memory leaks)",
            "concurrency": "race conditions and deadlocks"
        }

        return f"""
Find potential bugs with {severity} severity in {categories.get(category, category)}.

Focus areas:
1. **Logic Errors**: Off-by-one, null pointer, edge cases
2. **Security Issues**: Input validation, injection, auth bypass
3. **Performance**: Inefficient algorithms, memory leaks
4. **Concurrency**: Race conditions, deadlocks
5. **Error Handling**: Missing try-catch, unhandled exceptions

Use code://search to find suspicious patterns.
Provide specific vulnerabilities with file:line references and fix suggestions.
""".strip()
```

**Tests**: Test prompt generation, test parameters substitution

**Temps estimé**: 2h

---

#### Sub-Story 23.10.2: Test Generation Prompts (0.5 pt)

**Objectif**: Prompts pour génération tests

**Fichier**: `api/mcp/tools/prompt_tools.py` (ajouter)

**Contenu**:
```python
@mcp.prompt()
def generate_tests(
    chunk_id: str,
    test_type: str = "unit",
    coverage_target: int = 80
) -> str:
    """
    Generate prompt to create tests for code chunk.

    Args:
        chunk_id: UUID of code chunk to test
        test_type: Type of tests (unit, integration, e2e)
        coverage_target: Target coverage percentage
    """
    test_frameworks = {
        "unit": "pytest (Python), Jest (JS), JUnit (Java)",
        "integration": "pytest with fixtures, Testcontainers",
        "e2e": "Playwright, Cypress, Selenium"
    }

    return f"""
Generate {test_type} tests for code chunk {chunk_id} targeting {coverage_target}% coverage.

Test Requirements:
1. **Framework**: {test_frameworks.get(test_type, "appropriate framework")}
2. **Coverage Target**: {coverage_target}%
3. **Test Cases**:
   - Happy path (expected behavior)
   - Edge cases (boundaries, empty inputs)
   - Error cases (exceptions, invalid inputs)
   - Integration scenarios (if applicable)

Steps:
1. Use code://chunk/{chunk_id} to view the code
2. Use graph://callers/{chunk_id} to understand usage context
3. Generate comprehensive test suite with:
   - Setup/teardown fixtures
   - Mocking for dependencies
   - Assertions for expected behavior
   - Clear test names and documentation

Provide complete, runnable test code with comments.
""".strip()
```

**Temps estimé**: 1.5h

---

#### Sub-Story 23.10.3: Code Explanation Prompts (0.5 pt)

**Objectif**: Prompts pour expliquer code

**Fichier**: `api/mcp/tools/prompt_tools.py` (ajouter)

**Contenu**:
```python
@mcp.prompt()
def explain_code(
    chunk_id: str,
    level: str = "detailed",
    audience: str = "developer"
) -> str:
    """
    Generate prompt to explain code chunk.

    Args:
        chunk_id: UUID of code chunk to explain
        level: Explanation level (brief, detailed, comprehensive)
        audience: Target audience (beginner, developer, architect)
    """
    level_details = {
        "brief": "High-level summary (1-2 paragraphs)",
        "detailed": "Detailed explanation with examples",
        "comprehensive": "Deep dive with context, alternatives, trade-offs"
    }

    audience_focus = {
        "beginner": "Simple language, no jargon, step-by-step",
        "developer": "Technical details, patterns, best practices",
        "architect": "Design decisions, trade-offs, scalability"
    }

    return f"""
Explain code chunk {chunk_id} at {level} level for {audience} audience.

Explanation Style:
- **Level**: {level_details.get(level, "appropriate detail")}
- **Audience**: {audience_focus.get(audience, "general technical")}

Required Sections:
1. **Purpose**: What does this code do?
2. **How It Works**: Step-by-step explanation
3. **Key Concepts**: Important patterns, algorithms, data structures
4. **Dependencies**: What it relies on (use graph://callees)
5. **Usage**: How it's used in the codebase (use graph://callers)
6. **Context**: Why it exists, historical decisions

Use code://chunk/{chunk_id} to view the code.
Provide clear, well-structured explanation with code snippets if helpful.
""".strip()
```

**Temps estimé**: 1.5h

---

#### Sub-Story 23.10.4: Security Audit Prompt (0.5 pt)

**Objectif**: Prompt pour audit sécurité

**Fichier**: `api/mcp/tools/prompt_tools.py` (ajouter)

**Contenu**:
```python
@mcp.prompt()
def security_audit(
    scope: str = "all",
    compliance: str = "owasp"
) -> str:
    """
    Generate prompt for security audit.

    Args:
        scope: Audit scope (all, authentication, input-validation, etc.)
        compliance: Compliance standard (owasp, cwe, pci-dss, etc.)
    """
    scopes = {
        "all": "complete codebase",
        "authentication": "authentication and authorization",
        "input-validation": "user input handling",
        "data-protection": "sensitive data handling",
        "api-security": "API endpoints and CORS"
    }

    standards = {
        "owasp": "OWASP Top 10 2021",
        "cwe": "CWE Top 25 Most Dangerous Software Weaknesses",
        "pci-dss": "PCI DSS 3.2.1 (payment card data)",
        "hipaa": "HIPAA (healthcare data)"
    }

    return f"""
Perform security audit of {scopes.get(scope, scope)} against {standards.get(compliance, compliance)}.

Audit Checklist:
1. **Injection Vulnerabilities**: SQL, NoSQL, command injection
2. **Authentication/Authorization**: Broken access control, weak passwords
3. **Sensitive Data Exposure**: Unencrypted data, hardcoded secrets
4. **XML External Entities (XXE)**: XML parsing vulnerabilities
5. **Security Misconfiguration**: Default credentials, unnecessary services
6. **Cross-Site Scripting (XSS)**: Input sanitization, output encoding
7. **Insecure Deserialization**: Object injection attacks
8. **Using Components with Known Vulnerabilities**: Outdated dependencies
9. **Insufficient Logging & Monitoring**: Missing audit trails
10. **Server-Side Request Forgery (SSRF)**: Unvalidated URLs

Tools:
- Use code://search with security-focused queries (e.g., "password", "api_key", "eval(")
- Use graph://callers to trace data flow for sensitive functions
- Check for hardcoded credentials, weak crypto, missing validation

Provide:
- **Severity**: Critical, High, Medium, Low for each finding
- **Location**: Specific file:line references
- **Remediation**: How to fix with code examples
- **References**: CWE/CVE numbers if applicable
""".strip()
```

**Temps estimé**: 2h

---

## 📊 RÉSUMÉ COMPLET PHASE 2

### Story 23.4: Code Graph Tools ✅
- 23.4.1: Graph Models (1.5h)
- 23.4.2: Get Code Graph Resource (2.5h)
- 23.4.3: Find Callers Resource (2h)
- 23.4.4: Find Callees Resource (1.5h)
- 23.4.5: Graph Pagination (1.5h)
- 23.4.6: Performance & Caching (2h)
**Total: 11h** (6 sub-stories)

### Story 23.5: Project Indexing ✅
- 23.5.1: Index Project Tool (2.5h)
- 23.5.2: Reindex File Tool (1.5h)
- 23.5.3: Get Index Status Resource (1.5h)
- 23.5.4: Progress Streaming (1.5h)
**Total: 7h** (4 sub-stories)

### Story 23.6: Analytics & Observability ✅
- 23.6.1: Clear Cache Tool (1.5h)
- 23.6.2: Get Cache Stats Resource (1.5h)
- 23.6.3: Get Search Analytics Resource (2h)
- 23.6.4: Real-Time Stats SSE (2h)
**Total: 7h** (4 sub-stories)

### Story 23.10: Prompts Library ✅
- 23.10.1: Core Analysis Prompts (2h)
- 23.10.2: Test Generation Prompts (1.5h)
- 23.10.3: Code Explanation Prompts (1.5h)
- 23.10.4: Security Audit Prompt (2h)
**Total: 7h** (4 sub-stories)

---

## 📈 ESTIMATION PHASE 2 FINALE

| Story | Points | Sub-Stories | Heures | Ratio |
|-------|--------|-------------|--------|-------|
| 23.4 | 3 pt | 6 | 11h | 3.7h/pt |
| 23.5 | 2 pt | 4 | 7h | 3.5h/pt |
| 23.6 | 2 pt | 4 | 7h | 3.5h/pt |
| 23.10 | 2 pt | 4 | 7h | 3.5h/pt |
| **TOTAL** | **9 pt** | **18** | **32h** | **3.6h/pt** |

**Ratio cohérent**: ~3.5-4h par story point (réaliste avec découpage granulaire)

---

## 🎯 PRIORITÉS D'IMPLÉMENTATION PHASE 2

### Semaine 1 (Stories 23.4 + 23.5)
**Focus**: Graph + Indexing (fondations)
- Jour 1-3: Story 23.4 (Code Graph, 11h)
- Jour 4-5: Story 23.5 (Indexing, 7h)
**Validation**: MCP Inspector + tests pytest

### Semaine 2 (Stories 23.6 + 23.10)
**Focus**: Analytics + Prompts (polish)
- Jour 1-2: Story 23.6 (Analytics, 7h)
- Jour 3-4: Story 23.10 (Prompts, 7h)
- Jour 5: Buffer + documentation
**Validation**: End-to-end workflow avec Claude Desktop

---

## ✅ ACCEPTANCE CRITERIA PHASE 2

### Story 23.4: Code Graph ✅
- [ ] Resource `graph://nodes/{chunk_id}` retourne graphe valide
- [ ] Pagination fonctionne (>100 nodes)
- [ ] Filters par relation_types fonctionnels
- [ ] Resource `graph://callers` trouve tous callers
- [ ] Resource `graph://callees` trouve tous callees
- [ ] Cache hit rate > 80% (2ème appel)
- [ ] Query time < 200ms (graphe cached)

### Story 23.5: Project Indexing ✅
- [ ] Tool `index_project` indexe projet complet
- [ ] Progress reporting fonctionne (0-100%)
- [ ] Elicitation pour confirmation reindex
- [ ] Tool `reindex_file` met à jour fichier unique
- [ ] Resource `project://status` retourne statut correct
- [ ] Resource links présents dans résultats
- [ ] Indexing complète en < 5min (projet test 1000 fichiers)

### Story 23.6: Analytics ✅
- [ ] Tool `clear_cache` avec elicitation confirmation
- [ ] Resource `cache://stats` retourne stats L1/L2/L3
- [ ] Resource `analytics://search` retourne métriques EPIC-22
- [ ] SSE stream emits events every 5s (HTTP transport)
- [ ] Cache hit rate > 90% affiché correctement

### Story 23.10: Prompts ✅
- [ ] 6+ prompts exposés via MCP
- [ ] Prompts visibles dans Claude Desktop UI dropdown
- [ ] Paramètres utilisateur fonctionnels
- [ ] Prompt `analyze_codebase` génère template utile
- [ ] Prompt `generate_tests` avec chunk_id référence
- [ ] Prompt `security_audit` avec compliance standards

---

## 🚀 PROCHAINE ÉTAPE

Phase 2 complète! Options:

1. **Créer Phase 3** (Stories 23.7-23.9+23.11-23.12, 6 pts, ~18-24h)
2. **Créer EPIC-23_README.md officiel** avec Phases 1-2 complètes
3. **Commencer implémentation** Phase 1 (Story 23.1.1)

Dis-moi ce que tu préfères! 🎯

---

**Status**: ✅ PHASE 2 DÉCOUPAGE COMPLET
**Sub-stories créées**: 18/18 (100%)
**Temps total Phase 2**: 32h
**Prêt pour**: Phase 3 ou EPIC README officiel
