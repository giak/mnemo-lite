# EPIC-23 Story 23.10 ULTRATHINK - Prompts Library

**Story**: Prompts Library (MCP Prompt Templates)
**Points**: 2 pts
**Estimated Time**: ~7h
**Date**: 2025-10-28
**Status**: 🧠 DESIGN ANALYSIS (Pre-Implementation)

---

## 📋 Executive Summary

Story 23.10 implements **6 MCP prompt templates** that provide pre-written, parameterized prompts for common code analysis tasks. These prompts appear in Claude Desktop UI and guide users to leverage MnemoLite's MCP capabilities effectively.

**Key Insight**: Prompts are **NOT executable code** - they generate text prompts that guide LLM interactions. They help users discover and use MnemoLite's Tools and Resources by providing structured templates.

### Deliverables (4 Sub-Stories)
1. ✅ **Core Analysis Prompts** (0.5 pt, ~2h): `analyze_codebase`, `refactor_suggestions`, `find_bugs`
2. ✅ **Test Generation Prompt** (0.5 pt, ~1.5h): `generate_tests`
3. ✅ **Code Explanation Prompt** (0.5 pt, ~1.5h): `explain_code`
4. ✅ **Security Audit Prompt** (0.5 pt, ~2h): `security_audit`

### Decision Summary
- ✅ **Single file**: `api/mnemo_mcp/prompts.py` (not `prompt_tools.py`)
- ✅ **Registration function**: `register_prompts(mcp: FastMCP)`
- ✅ **No Pydantic models**: Prompts return plain strings (not models)
- ✅ **No unit tests**: Prompts are text templates (testing would be trivial string comparison)
- ✅ **Integration with existing tools/resources**: Prompts reference `code://search`, `graph://nodes`, etc.
- ✅ **MCP 2025-06-18 compliant**: Use `@mcp.prompt()` decorator

---

## 🎯 Story Objectives

### Primary Goal
Provide **6 pre-written prompt templates** that:
1. Guide users to explore codebases effectively
2. Leverage MnemoLite's semantic search and graph navigation
3. Follow best practices for code analysis, testing, security
4. Reduce cognitive load (users don't start from blank prompt)

### Success Criteria
- ✅ 6 prompts registered in MCP server
- ✅ Prompts appear in Claude Desktop UI
- ✅ Prompts accept parameters (language, severity, chunk_id, etc.)
- ✅ Prompts reference MnemoLite MCP capabilities (search_code, graph resources)
- ✅ Prompts follow consistent structure (clear sections, actionable guidance)

---

## 🏗️ Architecture Analysis

### MCP Prompts Specification

According to MCP 2025-06-18 spec, prompts are:
- **User-facing templates**: Appear in Claude Desktop UI for quick selection
- **Parameterized**: Accept arguments to customize template
- **Text output**: Return formatted string (not structured data)
- **Discovery mechanism**: Help users discover MCP capabilities

**Key Difference from Tools/Resources**:
- **Tools**: Executable operations (write_memory, index_project)
- **Resources**: Read operations (cache://stats, graph://nodes)
- **Prompts**: Text templates that **guide** LLM to use Tools/Resources

### FastMCP Implementation

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="mnemolite")

@mcp.prompt()
def analyze_codebase(language: str = "all", focus: str = "architecture") -> str:
    """
    Generate prompt to analyze codebase architecture.

    This docstring appears in Claude Desktop UI when selecting prompt.

    Args:
        language: Language to focus on (all, python, javascript, etc.)
        focus: Analysis focus (architecture, patterns, complexity, etc.)

    Returns:
        Formatted prompt text (NOT a Pydantic model)
    """
    return f"""
Analyze the {language} codebase with focus on {focus}.

Please provide:
1. **Architecture Overview**: High-level structure
2. **Design Patterns**: MVC, Repository, Factory, etc.
...
Use code://search to explore semantically.
""".strip()
```

**Observations**:
1. **Decorator**: `@mcp.prompt()` (not `@mcp.tool()` or `@mcp.resource()`)
2. **Return type**: `str` (plain text, not Pydantic model)
3. **Parameters**: Function signature defines prompt parameters
4. **Docstring**: Shown in Claude Desktop UI (important for UX)
5. **No Context**: Prompts don't receive `Context` object (they're not async operations)

### Integration Points

**Prompts Reference MnemoLite MCP Capabilities**:
1. `code://search` → Tool `search_code` (Story 23.2)
2. `graph://nodes/{chunk_id}` → Resource `graph://nodes` (Story 23.4)
3. `graph://callers/{name}` → Resource `graph://callers` (Story 23.4)
4. `graph://callees/{name}` → Resource `graph://callees` (Story 23.4)
5. `memories://search/{query}` → Resource `memories://search` (Story 23.3)
6. `index://status/{repository}` → Resource `index://status` (Story 23.5)

**Example**: `analyze_codebase` prompt might say:
```
Use code://search to find key architectural patterns.
Use graph://nodes to understand module relationships.
Use memories://search/architecture to review past decisions.
```

This **guides** the LLM to leverage MnemoLite's capabilities without requiring the user to know exact syntax.

---

## 📦 Implementation Design

### File Structure

```
api/mnemo_mcp/
  prompts.py          # NEW - All 6 prompt templates
  server.py           # MODIFIED - Register prompts in create_mcp_server()
```

**Why Single File?**
- Prompts are simple text templates (no complex logic)
- All prompts share similar structure (sections, tool references)
- Easy to maintain and discover
- Similar to how FastMCP examples organize prompts

### Prompts Overview

#### 1. analyze_codebase

**Purpose**: Generate comprehensive architecture analysis prompt

**Parameters**:
- `language: str = "all"` - Language to focus on (all, python, javascript, go, etc.)
- `focus: str = "architecture"` - Analysis focus (architecture, patterns, complexity, dependencies)

**Prompt Structure**:
```
Analyze the {language} codebase with focus on {focus}.

Please provide:
1. **Architecture Overview**: High-level structure and patterns
2. **Design Patterns**: Identified patterns (MVC, Repository, DIP, etc.)
3. **Code Organization**: Directory structure and modularity
4. **Dependencies**: External libraries and internal coupling
5. **Strengths**: What's well-designed
6. **Improvement Opportunities**: Potential refactoring

Use code://search to explore the codebase semantically.
Use graph://nodes to understand relationships.
Use memories://search/architecture to review past decisions.
```

**MCP Integration**:
- References `search_code` tool
- References `graph://nodes` resource
- References `memories://search` resource

**Estimated Time**: 30 minutes

---

#### 2. refactor_suggestions

**Purpose**: Find refactoring opportunities

**Parameters**:
- `focus: str = "all"` - Focus area (all, duplication, complexity, naming, structure)
- `severity: str = "medium"` - Severity level (low, medium, high)

**Prompt Structure**:
```
Find refactoring opportunities with {severity} severity focus on {focus}.

Criteria:
- **Severity**: {low/medium/high description}
- **Focus**: {focus area}

Please identify:
1. **Code Duplication**: Similar code that could be abstracted
2. **Complexity**: High cyclomatic complexity (>10)
3. **Naming Issues**: Unclear or inconsistent names
4. **Structure**: Better organization opportunities
5. **Patterns**: Missing or misused design patterns

Use code://search to detect patterns.
Use graph://callers and graph://callees to understand impact.
Provide specific file:line references with fix suggestions.
```

**Severity Descriptions**:
- **low**: Minor improvements (style, naming, comments)
- **medium**: Moderate improvements (structure, duplication, simplification)
- **high**: Major refactoring (architecture, design patterns, abstractions)

**Estimated Time**: 30 minutes

---

#### 3. find_bugs

**Purpose**: Identify potential bugs

**Parameters**:
- `severity: str = "high"` - Bug severity (high, medium, low)
- `category: str = "all"` - Bug category (all, logic, security, performance, concurrency)

**Prompt Structure**:
```
Find potential bugs with {severity} severity in {category}.

Focus areas:
1. **Logic Errors**: Off-by-one, null checks, edge cases
2. **Security Issues**: Injection, XSS, auth bypass, hardcoded secrets
3. **Performance**: N+1 queries, memory leaks, inefficient algorithms
4. **Concurrency**: Race conditions, deadlocks, thread safety
5. **Error Handling**: Missing try-catch, unhandled exceptions

Use code://search to find suspicious patterns (e.g., "eval(", "exec(", "password =").
Use graph://callers to trace data flow.
Provide specific vulnerabilities with file:line references and fix suggestions.
```

**Bug Categories**:
- **logic**: Logic errors (off-by-one, null pointer, edge cases)
- **security**: Security vulnerabilities (injection, XSS, auth bypass)
- **performance**: Performance issues (N+1, memory leaks, inefficient algorithms)
- **concurrency**: Race conditions, deadlocks, thread safety

**Estimated Time**: 30 minutes

---

#### 4. generate_tests

**Purpose**: Generate test suite for code chunk

**Parameters**:
- `chunk_id: str` - UUID of code chunk to test
- `test_type: str = "unit"` - Test type (unit, integration, e2e)
- `coverage_target: int = 80` - Target coverage percentage

**Prompt Structure**:
```
Generate {test_type} tests for code chunk {chunk_id} targeting {coverage_target}% coverage.

Test Requirements:
1. **Framework**: {pytest (Python), Jest (JS), JUnit (Java)}
2. **Coverage Target**: {coverage_target}%
3. **Test Cases**:
   - Happy path (expected behavior)
   - Edge cases (boundaries, empty inputs, null)
   - Error cases (exceptions, invalid inputs)
   - Integration scenarios (if applicable)

Steps:
1. Use graph://nodes/{chunk_id} to view the code
2. Use graph://callers/{chunk_id} to understand usage context
3. Generate comprehensive test suite with:
   - Setup/teardown fixtures
   - Mocking for dependencies
   - Assertions for expected behavior
   - Clear test names (test_<action>_<expected_result>)

Provide complete, runnable test code with comments.
```

**Test Frameworks by Language**:
- **Python**: pytest, unittest
- **JavaScript**: Jest, Mocha, Jasmine
- **TypeScript**: Jest, Vitest
- **Java**: JUnit, TestNG
- **Go**: testing package

**Estimated Time**: 1.5 hours

---

#### 5. explain_code

**Purpose**: Explain code chunk for different audiences

**Parameters**:
- `chunk_id: str` - UUID of code chunk to explain
- `level: str = "detailed"` - Explanation level (brief, detailed, comprehensive)
- `audience: str = "developer"` - Target audience (beginner, developer, architect)

**Prompt Structure**:
```
Explain code chunk {chunk_id} at {level} level for {audience} audience.

Explanation Style:
- **Level**: {brief/detailed/comprehensive description}
- **Audience**: {beginner/developer/architect focus}

Required Sections:
1. **Purpose**: What does this code do?
2. **How It Works**: Step-by-step explanation
3. **Key Concepts**: Patterns, algorithms, data structures
4. **Dependencies**: What it relies on (use graph://callees/{chunk_id})
5. **Usage**: How it's used (use graph://callers/{chunk_id})
6. **Context**: Why it exists, design decisions

Use graph://nodes/{chunk_id} to view the code with metadata.
Provide clear, well-structured explanation with code snippets if helpful.
```

**Explanation Levels**:
- **brief**: High-level summary (1-2 paragraphs)
- **detailed**: Detailed explanation with examples (5-10 paragraphs)
- **comprehensive**: Deep dive with context, alternatives, trade-offs (full article)

**Audience Focus**:
- **beginner**: Simple language, no jargon, step-by-step, analogies
- **developer**: Technical details, patterns, best practices, trade-offs
- **architect**: Design decisions, scalability, alternatives, business impact

**Estimated Time**: 1.5 hours

---

#### 6. security_audit

**Purpose**: Comprehensive security audit

**Parameters**:
- `scope: str = "all"` - Audit scope (all, authentication, input-validation, data-protection, api-security)
- `compliance: str = "owasp"` - Compliance standard (owasp, cwe, pci-dss, hipaa)

**Prompt Structure**:
```
Perform security audit of {scope} against {compliance standard}.

Audit Checklist (OWASP Top 10 2021):
1. **Injection Vulnerabilities**: SQL, NoSQL, command injection, LDAP
2. **Authentication/Authorization**: Broken access control, weak passwords
3. **Sensitive Data Exposure**: Unencrypted data, hardcoded secrets
4. **XML External Entities (XXE)**: XML parsing vulnerabilities
5. **Security Misconfiguration**: Default credentials, unnecessary services
6. **Cross-Site Scripting (XSS)**: Input sanitization, output encoding
7. **Insecure Deserialization**: Object injection attacks
8. **Components with Known Vulnerabilities**: Outdated dependencies
9. **Insufficient Logging & Monitoring**: Missing audit trails
10. **Server-Side Request Forgery (SSRF)**: Unvalidated URLs

Tools:
- Use code://search with security queries (e.g., "password", "api_key", "eval(", "exec(")
- Use graph://callers to trace data flow for sensitive functions
- Check for hardcoded credentials, weak crypto (MD5, SHA1), missing validation

Provide:
- **Severity**: Critical, High, Medium, Low (CVSS scoring)
- **Location**: Specific file:line references
- **Remediation**: How to fix with code examples
- **References**: CWE/CVE numbers if applicable
```

**Compliance Standards**:
- **owasp**: OWASP Top 10 2021 (web application security)
- **cwe**: CWE Top 25 Most Dangerous Software Weaknesses
- **pci-dss**: PCI DSS 3.2.1 (payment card data)
- **hipaa**: HIPAA (healthcare data protection)

**Security Scopes**:
- **all**: Complete codebase scan
- **authentication**: Auth/authz mechanisms
- **input-validation**: User input handling (forms, APIs, uploads)
- **data-protection**: Encryption, secrets management, PII handling
- **api-security**: API endpoints, CORS, rate limiting, API keys

**Estimated Time**: 2 hours

---

## 🧪 Testing Strategy

### Why No Unit Tests?

**Prompts are text templates**, not executable logic:
1. No business logic to test (just string interpolation)
2. Testing would be trivial string comparison: `assert "analyze" in result`
3. No external dependencies (no database, no services)
4. No error conditions (parameters are type-checked by FastMCP)
5. Manual validation is sufficient (review prompt text for quality)

**Validation Approach**:
1. **Manual review**: Check prompt text for clarity, completeness
2. **Integration testing**: Test prompts in Claude Desktop UI
3. **User feedback**: Gather feedback on prompt usefulness (Story 23.7)

**If we were to write tests**, they would look like:
```python
def test_analyze_codebase_prompt():
    """Test analyze_codebase generates expected prompt."""
    result = analyze_codebase(language="python", focus="architecture")

    assert "python" in result.lower()
    assert "architecture" in result.lower()
    assert "code://search" in result
    assert "graph://nodes" in result
    # ... trivial string assertions
```

**Decision**: Skip unit tests for Story 23.10. Focus implementation time on prompt quality and coverage.

---

## 🔄 Integration with Existing Components

### Tools Integration

Prompts reference these MCP tools:
1. **search_code** (Story 23.2)
   - Used in: `analyze_codebase`, `refactor_suggestions`, `find_bugs`, `security_audit`
   - Example: `"Use code://search to find architectural patterns"`

### Resources Integration

Prompts reference these MCP resources:
1. **graph://nodes/{chunk_id}** (Story 23.4)
   - Used in: `analyze_codebase`, `generate_tests`, `explain_code`
   - Example: `"Use graph://nodes/{chunk_id} to view code with metadata"`

2. **graph://callers/{name}** (Story 23.4)
   - Used in: `refactor_suggestions`, `find_bugs`, `generate_tests`, `explain_code`, `security_audit`
   - Example: `"Use graph://callers to trace data flow"`

3. **graph://callees/{name}** (Story 23.4)
   - Used in: `refactor_suggestions`, `explain_code`
   - Example: `"Use graph://callees to understand dependencies"`

4. **memories://search/{query}** (Story 23.3)
   - Used in: `analyze_codebase`
   - Example: `"Use memories://search/architecture to review past decisions"`

5. **index://status/{repository}** (Story 23.5)
   - Could be used in: `analyze_codebase` (optional)
   - Example: `"Check index://status/default to ensure codebase is indexed"`

### User Discovery Flow

**How Users Discover Prompts**:
1. Open Claude Desktop
2. Connect to MnemoLite MCP server
3. Click "Prompts" in UI → See 6 prompts
4. Select prompt (e.g., "Analyze Codebase")
5. Fill parameters (language: "python", focus: "architecture")
6. Claude inserts generated prompt into conversation
7. User submits → Claude uses MCP tools/resources to answer

**Example User Flow**:
```
User: [Selects "Analyze Codebase" prompt, language="python", focus="patterns"]

Claude (auto-generated prompt):
"Analyze the python codebase with focus on patterns.
Please provide:
1. Architecture Overview: ...
2. Design Patterns: ...
Use code://search to explore..."

Claude (executes):
- Calls search_code("design patterns")
- Calls graph://nodes for key modules
- Analyzes results and provides comprehensive architecture report
```

---

## 📐 Design Decisions

### Decision 1: Single File vs Multiple Files

**Options**:
1. **Single file** (`prompts.py`): All 6 prompts in one file
2. **Multiple files**: Separate by category (analysis_prompts.py, test_prompts.py, security_prompts.py)

**Decision**: ✅ **Single file**

**Rationale**:
- Prompts are simple (10-30 lines each)
- Total ~200-300 lines (reasonable for single file)
- Easier to discover and maintain
- Consistent with FastMCP examples
- No complex dependencies between prompts

---

### Decision 2: Prompt Parameters Validation

**Options**:
1. **No validation**: Accept any parameter values
2. **Literal types**: Use `Literal["low", "medium", "high"]` for severity
3. **Manual validation**: Check parameters in prompt function

**Decision**: ✅ **No validation** (FastMCP handles basic type checking)

**Rationale**:
- Prompts are text templates (not executable code)
- Invalid parameters just produce suboptimal prompts (not errors)
- FastMCP validates parameter types automatically
- Users can still get value from prompts with unusual parameters
- Example: `severity="critical"` not in enum → still generates useful prompt

---

### Decision 3: Prompt Output Format

**Options**:
1. **Plain text**: Return raw string
2. **Markdown**: Return formatted markdown
3. **Structured**: Return JSON or Pydantic model

**Decision**: ✅ **Markdown-formatted text**

**Rationale**:
- MCP spec: Prompts return strings (not structured data)
- Markdown provides structure (headers, lists, code blocks)
- Claude renders markdown beautifully in UI
- Easy to read and parse for both humans and LLMs

---

### Decision 4: Tool/Resource References Format

**Options**:
1. **Natural language**: "Use the search code tool to find patterns"
2. **URI format**: "Use code://search to find patterns"
3. **Function calls**: "Call search_code(query='patterns')"

**Decision**: ✅ **URI format**

**Rationale**:
- Consistent with MCP resource URIs
- Clear, unambiguous reference to MCP capabilities
- Mirrors how resources are accessed (graph://nodes, memories://search)
- Easy for LLM to recognize and use
- Familiar to developers (similar to URL schemes)

---

### Decision 5: Prompt Complexity Level

**Options**:
1. **Simple**: Minimal guidance (1-2 sentences)
2. **Detailed**: Structured sections with examples (current approach)
3. **Comprehensive**: Extensive guidance with edge cases, examples, best practices

**Decision**: ✅ **Detailed** (structured sections)

**Rationale**:
- Simple prompts don't provide enough guidance (users struggle)
- Comprehensive prompts are overwhelming (too long, users skip)
- Detailed strikes balance: Clear structure, actionable guidance, not overwhelming
- 10-20 lines per prompt is sweet spot

---

## 🎯 Success Metrics

### Quantitative Metrics
- ✅ 6 prompts implemented
- ✅ All prompts registered in MCP server
- ✅ Prompts appear in Claude Desktop UI
- ✅ Parameters work correctly (type checking, defaults)

### Qualitative Metrics
- ✅ Prompts are clear and actionable
- ✅ Prompts reference MnemoLite MCP capabilities correctly
- ✅ Prompts follow consistent structure
- ✅ Prompts cover diverse use cases (analysis, testing, security, etc.)

### User Experience
- Users can quickly select prompts from Claude Desktop
- Users understand what each prompt does (clear docstrings)
- Users successfully use prompts to explore codebases
- Prompts reduce cognitive load (don't start from blank)

---

## 🚨 Risks & Mitigations

### Risk 1: Prompts Too Generic

**Risk**: Prompts might be too generic and not leverage MnemoLite's unique capabilities

**Likelihood**: Medium
**Impact**: Medium

**Mitigation**:
- ✅ Explicitly reference MnemoLite MCP tools/resources in prompts
- ✅ Provide concrete examples of tool usage (code://search, graph://nodes)
- ✅ Tailor prompts to code intelligence use cases (not generic ChatGPT prompts)

---

### Risk 2: Prompts Out of Sync with Tools/Resources

**Risk**: Tools/resources might change (rename, remove), breaking prompt references

**Likelihood**: Low
**Impact**: Low

**Mitigation**:
- ✅ Prompts reference stable URIs (unlikely to change)
- ✅ Document prompt maintenance in completion report
- ✅ Regular review during EPIC completion (Story 23.9)

---

### Risk 3: Prompt Quality Varies

**Risk**: Some prompts might be more useful than others

**Likelihood**: High
**Impact**: Low

**Mitigation**:
- ✅ Start with 6 core prompts (proven use cases)
- ✅ Gather user feedback in Story 23.7 (User Feedback & Edge Cases)
- ✅ Iterate on prompts based on usage patterns
- ✅ Add more prompts in future stories if needed

---

## 📝 Implementation Plan

### Phase 1: Core Prompts (2h)

**File**: `api/mnemo_mcp/prompts.py`

**Sub-Stories**:
1. **analyze_codebase** (30 min)
2. **refactor_suggestions** (30 min)
3. **find_bugs** (30 min)

**Deliverable**: 3 core analysis prompts

---

### Phase 2: Specialized Prompts (3h)

**File**: `api/mnemo_mcp/prompts.py` (append)

**Sub-Stories**:
4. **generate_tests** (1.5h)
5. **explain_code** (1.5h)

**Deliverable**: 2 specialized prompts

---

### Phase 3: Security Prompt (2h)

**File**: `api/mnemo_mcp/prompts.py` (append)

**Sub-Stories**:
6. **security_audit** (2h)

**Deliverable**: 1 security prompt

---

### Phase 4: Server Integration (30 min)

**File**: `api/mnemo_mcp/server.py`

**Changes**:
1. Import `register_prompts` from `mnemo_mcp.prompts`
2. Call `register_prompts(mcp)` in `create_mcp_server()`
3. Add logging: `logger.info("mcp.prompts.registered", prompts=6)`

**Deliverable**: Prompts registered in MCP server

---

## 🎓 Lessons from Previous Stories

### From Story 23.5 (Indexing)
- ✅ **Perfect estimation**: 7h actual vs 7h estimated
- ✅ **ULTRATHINK works**: Comprehensive planning prevents surprises
- ✅ **Simple is better**: Avoid over-engineering

### From Story 23.6 (Analytics)
- ✅ **Infrastructure reuse**: 85% reuse (CascadeCache, MetricsCollector)
- ✅ **Graceful degradation**: Always handle missing services
- ✅ **Logging**: Use structlog (not standard logging)

### Applied to Story 23.10
- ✅ **Keep it simple**: Prompts are text templates (no complex logic)
- ✅ **Reuse existing MCP components**: Reference tools/resources by URI
- ✅ **Focus on quality**: 6 great prompts > 20 mediocre prompts
- ✅ **No over-testing**: Skip unit tests for text templates

---

## 🎯 Completion Criteria

### Code
- ✅ `api/mnemo_mcp/prompts.py` created (6 prompts, ~300 lines)
- ✅ `api/mnemo_mcp/server.py` modified (register_prompts call)
- ✅ All prompts use `@mcp.prompt()` decorator
- ✅ All prompts have clear docstrings
- ✅ All prompts accept reasonable parameters
- ✅ All prompts return markdown-formatted strings

### Integration
- ✅ Prompts registered in MCP server
- ✅ Prompts appear in Claude Desktop UI
- ✅ Prompts reference MnemoLite tools/resources correctly

### Documentation
- ✅ Completion report created
- ✅ EPIC-23_PROGRESS_TRACKER.md updated
- ✅ EPIC-23_README.md updated

---

## 🚀 Next Steps After Completion

1. **Story 23.7** - Configuration & Utilities (1 pt, ~4h)
   - `switch_project` tool
   - `projects://list`, `config://languages` resources

2. **Story 23.8** - HTTP Transport Support (2 pts, ~8h)
   - HTTP/SSE server setup
   - OAuth 2.0 + PKCE authentication
   - SSE for real-time updates (deferred from Story 23.6)

3. **Story 23.9** - Documentation & Examples (1 pt, ~4h)
   - User guide & API reference
   - Developer guide & architecture docs

---

## 📊 Estimated Breakdown

| Phase | Sub-Stories | Time | Deliverables |
|-------|-------------|------|--------------|
| **Phase 1** | 3 core prompts | 2h | analyze_codebase, refactor_suggestions, find_bugs |
| **Phase 2** | 2 specialized | 3h | generate_tests, explain_code |
| **Phase 3** | 1 security | 2h | security_audit |
| **Phase 4** | Server integration | 30min | Register prompts in MCP server |
| **TOTAL** | **6 prompts** | **7.5h** | **prompts.py + server.py integration** |

**Buffer**: 30 min (for unforeseen issues)
**Final Estimate**: **7h** (consistent with 2 pts × 3.5h/pt)

---

## ✅ Pre-Implementation Checklist

- ✅ Story objectives clear
- ✅ MCP prompts specification understood
- ✅ FastMCP @mcp.prompt() decorator usage confirmed
- ✅ 6 prompts designed (analyze, refactor, bugs, tests, explain, security)
- ✅ Parameters defined for each prompt
- ✅ Prompt structure designed (sections, tool references)
- ✅ Integration points identified (tools/resources references)
- ✅ Testing strategy defined (manual validation, no unit tests)
- ✅ Implementation plan created (4 phases, 7h)
- ✅ Risks identified and mitigated
- ✅ Success criteria defined

---

**Status**: ✅ READY FOR IMPLEMENTATION

**Confidence**: 95% (Prompts are simple, well-defined, low risk)

**Recommendation**: **PROCEED** with implementation following 4-phase plan.
