"""
MCP Prompt Templates for MnemoLite (EPIC-23 Story 23.10).

Prompts are user-facing templates that appear in Claude Desktop UI.
They guide users to leverage MnemoLite's code intelligence capabilities.
"""

from mcp.server.fastmcp import FastMCP
import structlog

logger = structlog.get_logger()


def register_prompts(mcp: FastMCP) -> None:
    """
    Register all MCP prompt templates.

    Prompts provide pre-written, parameterized templates for common
    code analysis tasks. They appear in Claude Desktop UI and guide
    users to use MnemoLite's Tools and Resources effectively.

    Args:
        mcp: FastMCP server instance

    Prompts Registered:
        - analyze_codebase: Architecture and design patterns analysis
        - refactor_suggestions: Find refactoring opportunities
        - find_bugs: Identify potential bugs and vulnerabilities
        - generate_tests: Generate test suite for code chunk
        - explain_code: Explain code for different audiences
        - security_audit: Comprehensive security audit (OWASP, CWE)
    """

    # ========================================================================
    # Core Analysis Prompts (3)
    # ========================================================================

    @mcp.prompt()
    def analyze_codebase(language: str = "all", focus: str = "architecture") -> str:
        """
        Generate prompt to analyze codebase architecture and design patterns.

        Helps understand high-level structure, patterns, and organization.
        Useful for onboarding, architecture reviews, or refactoring planning.

        Args:
            language: Language to focus on (all, python, javascript, typescript, go, rust, java, etc.)
            focus: Analysis focus (architecture, patterns, complexity, dependencies, modularity)

        Returns:
            Formatted prompt text guiding comprehensive architecture analysis

        Examples:
            - analyze_codebase(language="python", focus="architecture")
            - analyze_codebase(language="all", focus="patterns")
            - analyze_codebase(language="javascript", focus="dependencies")
        """
        return f"""
Analyze the {language} codebase with focus on {focus}.

Please provide:

1. **Architecture Overview**: High-level structure and design philosophy
   - Layering (presentation, business logic, data access)
   - Module organization and boundaries
   - Key architectural patterns (MVC, Repository, DIP, CQRS, etc.)

2. **Design Patterns**: Identified patterns used throughout codebase
   - Creational patterns (Factory, Builder, Singleton)
   - Structural patterns (Adapter, Decorator, Facade)
   - Behavioral patterns (Strategy, Observer, Command)

3. **Code Organization**: Directory structure and modularity
   - Package/module structure
   - Separation of concerns
   - Coupling and cohesion analysis

4. **Dependencies**: External libraries and internal coupling
   - Third-party dependencies and versions
   - Internal module dependencies
   - Circular dependencies or tight coupling issues

5. **Strengths**: What's well-designed
   - Good practices and patterns
   - Clean, maintainable code areas
   - Scalable components

6. **Improvement Opportunities**: Potential refactoring or redesign
   - Areas with high complexity or technical debt
   - Missing abstractions or patterns
   - Modularity improvements

**Tools to Use**:
- Use `search_code` to explore the codebase semantically (e.g., "repository pattern", "factory", "dependency injection")
- Use `graph://nodes/{{chunk_id}}` to understand module relationships and dependencies
- Use `memories://search/architecture` to review past architectural decisions
- Use `index://status/{{repository}}` to check if codebase is fully indexed

Provide specific examples with file:line references where applicable.
""".strip()

    @mcp.prompt()
    def refactor_suggestions(focus: str = "all", severity: str = "medium") -> str:
        """
        Generate prompt to find refactoring opportunities.

        Identifies code smells, duplication, complexity, and structural issues.
        Useful for code reviews, technical debt reduction, or quality improvement.

        Args:
            focus: Focus area (all, duplication, complexity, naming, structure, patterns)
            severity: Severity level (low, medium, high)
                - low: Minor improvements (style, naming, comments)
                - medium: Moderate improvements (structure, duplication, simplification)
                - high: Major refactoring (architecture, design patterns, abstractions)

        Returns:
            Formatted prompt text guiding refactoring analysis

        Examples:
            - refactor_suggestions(focus="duplication", severity="high")
            - refactor_suggestions(focus="complexity", severity="medium")
            - refactor_suggestions(focus="all", severity="low")
        """
        severity_descriptions = {
            "low": "minor improvements (style, naming, comments, formatting)",
            "medium": "moderate improvements (structure, duplication, simplification)",
            "high": "major refactoring (architecture, design patterns, abstractions)"
        }

        severity_desc = severity_descriptions.get(severity, "all improvements")

        return f"""
Find refactoring opportunities with {severity} severity focusing on {focus}.

**Criteria**:
- **Severity**: {severity_desc}
- **Focus Area**: {focus}

Please identify:

1. **Code Duplication**: Similar code that could be abstracted
   - Repeated logic across files/functions
   - Copy-paste patterns
   - Opportunities for shared utilities or base classes

2. **Complexity**: Functions/classes with high cyclomatic complexity (>10)
   - Long functions (>50 lines)
   - Deep nesting (>4 levels)
   - Too many parameters (>5)
   - God classes or functions doing too much

3. **Naming Issues**: Unclear or inconsistent names
   - Vague names (e.g., "data", "temp", "helper")
   - Inconsistent naming conventions
   - Misleading or outdated names

4. **Structure**: Opportunities for better organization
   - Misplaced responsibilities
   - Missing abstractions
   - Violation of Single Responsibility Principle
   - Feature envy (method using more of another class than its own)

5. **Patterns**: Missing or misused design patterns
   - Opportunities to apply patterns (Strategy, Factory, etc.)
   - Anti-patterns (God Object, Spaghetti Code, Shotgun Surgery)

**Tools to Use**:
- Use `search_code` to detect code patterns and duplication
- Use `graph://callers/{{qualified_name}}` to understand impact of changes
- Use `graph://callees/{{qualified_name}}` to analyze dependencies
- Use `memories://search/refactoring` to review past refactoring decisions

Provide specific file:line references with:
- **Issue**: What's wrong
- **Impact**: Why it matters
- **Suggestion**: How to fix (with code examples if helpful)
- **Effort**: Estimated time to refactor
""".strip()

    @mcp.prompt()
    def find_bugs(severity: str = "high", category: str = "all") -> str:
        """
        Generate prompt to find potential bugs and vulnerabilities.

        Identifies logic errors, security issues, performance problems, and more.
        Useful for code reviews, QA, or proactive bug prevention.

        Args:
            severity: Bug severity (high, medium, low)
            category: Bug category (all, logic, security, performance, concurrency)
                - logic: Logic errors (off-by-one, null checks, edge cases)
                - security: Security vulnerabilities (injection, XSS, auth bypass)
                - performance: Performance issues (N+1 queries, memory leaks)
                - concurrency: Race conditions, deadlocks, thread safety

        Returns:
            Formatted prompt text guiding bug detection analysis

        Examples:
            - find_bugs(severity="high", category="security")
            - find_bugs(severity="medium", category="logic")
            - find_bugs(severity="all", category="concurrency")
        """
        categories = {
            "all": "all categories",
            "logic": "logic errors (off-by-one, null checks, edge cases)",
            "security": "security vulnerabilities (injection, XSS, auth bypass, hardcoded secrets)",
            "performance": "performance issues (N+1 queries, memory leaks, inefficient algorithms)",
            "concurrency": "race conditions, deadlocks, thread safety issues"
        }

        category_desc = categories.get(category, category)

        return f"""
Find potential bugs with {severity} severity in {category_desc}.

**Focus Areas**:

1. **Logic Errors**: Off-by-one, null pointer, edge cases
   - Array/list index out of bounds
   - Null/None dereferencing without checks
   - Edge case handling (empty inputs, zero, negative numbers)
   - Integer overflow/underflow
   - Floating point comparison issues

2. **Security Issues**: Input validation, injection, auth bypass
   - SQL/NoSQL injection vulnerabilities
   - Cross-Site Scripting (XSS)
   - Command injection
   - Path traversal
   - Authentication/authorization bypass
   - Hardcoded credentials or API keys

3. **Performance**: Inefficient algorithms, memory leaks
   - N+1 query problems
   - Inefficient loops or nested iterations
   - Memory leaks (unclosed resources, circular references)
   - Excessive object creation
   - Missing indexes on database queries

4. **Concurrency**: Race conditions, deadlocks
   - Shared mutable state without synchronization
   - Deadlock potential (lock ordering issues)
   - Missing volatile/atomic operations
   - Thread-unsafe data structures
   - Race conditions in async code

5. **Error Handling**: Missing try-catch, unhandled exceptions
   - Missing error handling for file I/O, network, database
   - Swallowed exceptions (empty catch blocks)
   - Improper error propagation
   - Missing input validation

**Tools to Use**:
- Use `search_code` with security-focused queries:
  - "password =", "api_key =", "secret ="
  - "eval(", "exec(", "system(", "shell_exec"
  - "SELECT * FROM", "INSERT INTO"
  - "innerHTML", "dangerouslySetInnerHTML"
- Use `graph://callers/{{qualified_name}}` to trace data flow for sensitive functions
- Use `graph://callees/{{qualified_name}}` to check for dangerous function calls

Provide specific vulnerabilities with:
- **Severity**: Critical, High, Medium, Low
- **Location**: file:line references
- **Description**: What's the bug and why it's dangerous
- **Exploit Scenario**: How it could be exploited (if applicable)
- **Fix**: How to fix with code examples
""".strip()

    # ========================================================================
    # Test Generation Prompt (1)
    # ========================================================================

    @mcp.prompt()
    def generate_tests(
        chunk_id: str,
        test_type: str = "unit",
        coverage_target: int = 80
    ) -> str:
        """
        Generate prompt to create comprehensive test suite for code chunk.

        Creates unit, integration, or e2e tests with proper fixtures, mocks, assertions.
        Useful for TDD, increasing coverage, or adding tests to legacy code.

        Args:
            chunk_id: UUID of code chunk to test (from search_code or graph resources)
            test_type: Type of tests (unit, integration, e2e)
            coverage_target: Target coverage percentage (0-100)

        Returns:
            Formatted prompt text guiding test generation

        Examples:
            - generate_tests(chunk_id="abc-123-def", test_type="unit", coverage_target=90)
            - generate_tests(chunk_id="xyz-789", test_type="integration", coverage_target=80)
        """
        test_frameworks = {
            "unit": "pytest (Python), Jest (JavaScript), JUnit (Java), testing (Go)",
            "integration": "pytest with fixtures/Testcontainers (Python), Supertest (JS), TestNG (Java)",
            "e2e": "Playwright/Selenium (web), Cypress (frontend), pytest-bdd (Python)"
        }

        framework_desc = test_frameworks.get(test_type, "appropriate testing framework")

        return f"""
Generate {test_type} tests for code chunk {chunk_id} targeting {coverage_target}% coverage.

**Test Requirements**:

1. **Framework**: {framework_desc}
2. **Coverage Target**: {coverage_target}%
3. **Test Cases to Cover**:
   - **Happy Path**: Expected behavior with valid inputs
   - **Edge Cases**: Boundaries (empty, null, zero, max values)
   - **Error Cases**: Invalid inputs, exceptions, error conditions
   - **Integration Scenarios**: Interaction with dependencies (if applicable)

**Steps**:

1. **Understand the Code**:
   - Use `graph://nodes/{chunk_id}` to view the code chunk with metadata
   - Identify function signature, parameters, return type
   - Understand the purpose and business logic

2. **Analyze Dependencies**:
   - Use `graph://callees/{chunk_id}` to see what functions/classes it depends on
   - Identify external dependencies that need mocking
   - Understand side effects (database, API calls, file I/O)

3. **Analyze Usage Context**:
   - Use `graph://callers/{chunk_id}` to understand how it's used in practice
   - Identify common usage patterns and edge cases
   - Understand integration points

4. **Generate Test Suite** with:
   - **Setup/Teardown Fixtures**: Database, files, test data
   - **Mocking**: Mock external dependencies (API, database, file system)
   - **Test Methods**: Clear names following pattern `test_<action>_<expected_result>`
   - **Assertions**: Verify expected behavior, return values, state changes
   - **Documentation**: Comments explaining test purpose and edge cases

**Example Test Structure** (pytest):
```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def sample_data():
    \"\"\"Fixture providing test data.\"\"\"
    return {{"key": "value"}}

def test_function_happy_path(sample_data):
    \"\"\"Test function with valid inputs.\"\"\"
    result = my_function(sample_data)
    assert result == expected_value

def test_function_edge_case_empty_input():
    \"\"\"Test function with empty input.\"\"\"
    result = my_function({{}})
    assert result == default_value

@patch('module.external_api')
def test_function_with_mock(mock_api):
    \"\"\"Test function with mocked external dependency.\"\"\"
    mock_api.return_value = {{"status": "ok"}}
    result = my_function()
    assert result["status"] == "ok"
    mock_api.assert_called_once()
```

Provide complete, runnable test code with:
- Clear test names and documentation
- Comprehensive coverage of scenarios
- Proper fixtures and mocking
- Assertions for all expected behaviors
""".strip()

    # ========================================================================
    # Code Explanation Prompt (1)
    # ========================================================================

    @mcp.prompt()
    def explain_code(
        chunk_id: str,
        level: str = "detailed",
        audience: str = "developer"
    ) -> str:
        """
        Generate prompt to explain code chunk for different audiences.

        Creates clear, well-structured explanations tailored to audience level.
        Useful for documentation, onboarding, code reviews, or learning.

        Args:
            chunk_id: UUID of code chunk to explain (from search_code or graph resources)
            level: Explanation level (brief, detailed, comprehensive)
                - brief: High-level summary (1-2 paragraphs)
                - detailed: Detailed explanation with examples (5-10 paragraphs)
                - comprehensive: Deep dive with context, alternatives, trade-offs
            audience: Target audience (beginner, developer, architect)
                - beginner: Simple language, no jargon, step-by-step, analogies
                - developer: Technical details, patterns, best practices, trade-offs
                - architect: Design decisions, scalability, alternatives, business impact

        Returns:
            Formatted prompt text guiding code explanation

        Examples:
            - explain_code(chunk_id="abc-123", level="brief", audience="beginner")
            - explain_code(chunk_id="xyz-789", level="detailed", audience="developer")
            - explain_code(chunk_id="def-456", level="comprehensive", audience="architect")
        """
        level_details = {
            "brief": "High-level summary (1-2 paragraphs) - what it does and why",
            "detailed": "Detailed explanation with examples (5-10 paragraphs) - how it works step-by-step",
            "comprehensive": "Deep dive with context, alternatives, trade-offs (full article) - comprehensive analysis"
        }

        audience_focus = {
            "beginner": "Simple language, no jargon, step-by-step explanations, analogies and examples",
            "developer": "Technical details, design patterns, best practices, implementation trade-offs",
            "architect": "Design decisions, scalability implications, architectural alternatives, business impact"
        }

        level_desc = level_details.get(level, "appropriate level of detail")
        audience_desc = audience_focus.get(audience, "general technical audience")

        return f"""
Explain code chunk {chunk_id} at {level} level for {audience} audience.

**Explanation Style**:
- **Level**: {level_desc}
- **Audience Focus**: {audience_desc}

**Required Sections**:

1. **Purpose**: What does this code do?
   - High-level functionality
   - Business value or use case
   - Role in the larger system

2. **How It Works**: Step-by-step explanation
   - Algorithm or logic flow
   - Key operations and transformations
   - Important variables and data structures
   - Control flow (loops, conditionals, error handling)

3. **Key Concepts**: Important patterns, algorithms, data structures
   - Design patterns used (if any)
   - Algorithms (sorting, searching, parsing, etc.)
   - Data structures (lists, maps, trees, etc.)
   - Programming paradigms (OOP, functional, etc.)

4. **Dependencies**: What it relies on
   - Use `graph://callees/{chunk_id}` to identify dependencies
   - External libraries or frameworks
   - Internal modules or classes
   - Database, API, or file system access

5. **Usage**: How it's used in the codebase
   - Use `graph://callers/{chunk_id}` to find usage examples
   - Common usage patterns
   - Integration points
   - Public vs private interface

6. **Context**: Why it exists, design decisions
   - Historical context (why was it written this way?)
   - Design alternatives considered
   - Trade-offs made (performance vs readability, etc.)
   - Future improvements or known limitations

**Tools to Use**:
- Use `graph://nodes/{chunk_id}` to view the code chunk with metadata (type, language, LOC)
- Use `graph://callees/{chunk_id}` to understand what this code depends on
- Use `graph://callers/{chunk_id}` to see how it's used throughout the codebase
- Use `memories://search/{{relevant_topic}}` to find related architectural decisions or notes

**Explanation Guidelines**:
- Start with the big picture, then dive into details
- Use code snippets to illustrate key points
- Provide examples of input/output or state changes
- Explain "why" not just "what" (rationale behind design decisions)
- Highlight potential gotchas or common mistakes
- Suggest further reading or related concepts (if comprehensive level)

Provide a clear, well-structured explanation that helps the {audience} understand not just what the code does, but why it does it that way.
""".strip()

    # ========================================================================
    # Security Audit Prompt (1)
    # ========================================================================

    @mcp.prompt()
    def security_audit(scope: str = "all", compliance: str = "owasp") -> str:
        """
        Generate prompt for comprehensive security audit.

        Identifies security vulnerabilities against industry standards (OWASP, CWE, etc.).
        Useful for security reviews, compliance audits, or penetration testing preparation.

        Args:
            scope: Audit scope (all, authentication, input-validation, data-protection, api-security)
                - all: Complete codebase scan
                - authentication: Auth/authz mechanisms
                - input-validation: User input handling (forms, APIs, uploads)
                - data-protection: Encryption, secrets management, PII handling
                - api-security: API endpoints, CORS, rate limiting, API keys
            compliance: Compliance standard (owasp, cwe, pci-dss, hipaa)
                - owasp: OWASP Top 10 2021 (web application security)
                - cwe: CWE Top 25 Most Dangerous Software Weaknesses
                - pci-dss: PCI DSS 3.2.1 (payment card data security)
                - hipaa: HIPAA (healthcare data protection)

        Returns:
            Formatted prompt text guiding security audit

        Examples:
            - security_audit(scope="all", compliance="owasp")
            - security_audit(scope="authentication", compliance="cwe")
            - security_audit(scope="api-security", compliance="owasp")
        """
        scopes = {
            "all": "complete codebase",
            "authentication": "authentication and authorization mechanisms",
            "input-validation": "user input handling (forms, APIs, file uploads)",
            "data-protection": "sensitive data handling (encryption, secrets, PII)",
            "api-security": "API endpoints (CORS, rate limiting, authentication)"
        }

        standards = {
            "owasp": "OWASP Top 10 2021 (web application security)",
            "cwe": "CWE Top 25 Most Dangerous Software Weaknesses",
            "pci-dss": "PCI DSS 3.2.1 (payment card industry data security)",
            "hipaa": "HIPAA Security Rule (healthcare data protection)"
        }

        scope_desc = scopes.get(scope, scope)
        standard_desc = standards.get(compliance, compliance)

        return f"""
Perform comprehensive security audit of {scope_desc} against {standard_desc}.

**Audit Checklist - OWASP Top 10 2021**:

1. **A01:2021 - Broken Access Control**
   - Missing authorization checks
   - Insecure direct object references (IDOR)
   - Path traversal vulnerabilities
   - Privilege escalation

2. **A02:2021 - Cryptographic Failures**
   - Hardcoded secrets (passwords, API keys, tokens)
   - Weak encryption (MD5, SHA1, DES)
   - Unencrypted sensitive data in transit or at rest
   - Improper key management

3. **A03:2021 - Injection**
   - SQL injection (unsanitized database queries)
   - NoSQL injection (MongoDB, Redis)
   - Command injection (os.system, subprocess, exec)
   - LDAP, XPath, XML injection

4. **A04:2021 - Insecure Design**
   - Missing security controls in design
   - Lack of rate limiting or throttling
   - Missing input validation at design level
   - Insufficient threat modeling

5. **A05:2021 - Security Misconfiguration**
   - Default credentials or configurations
   - Verbose error messages exposing internals
   - Unnecessary features or services enabled
   - Missing security headers (CSP, HSTS, X-Frame-Options)

6. **A06:2021 - Vulnerable and Outdated Components**
   - Outdated dependencies with known CVEs
   - Unused dependencies increasing attack surface
   - Unmaintained libraries
   - Missing security patches

7. **A07:2021 - Identification and Authentication Failures**
   - Weak password policies
   - Missing multi-factor authentication
   - Session fixation vulnerabilities
   - Improper credential storage

8. **A08:2021 - Software and Data Integrity Failures**
   - Insecure deserialization (pickle, eval)
   - Missing integrity checks (HMAC, digital signatures)
   - Auto-update without verification
   - Untrusted CI/CD pipelines

9. **A09:2021 - Security Logging and Monitoring Failures**
   - Missing audit logs for critical operations
   - Insufficient logging of authentication failures
   - No monitoring for suspicious activity
   - Logs containing sensitive data

10. **A10:2021 - Server-Side Request Forgery (SSRF)**
    - Unvalidated URLs in API calls
    - Accessing internal resources via user input
    - Missing network segmentation
    - Bypass of IP allowlists

**Tools to Use**:
- Use `search_code` with security-focused queries:
  - Secrets: "password =", "api_key =", "secret =", "token ="
  - Dangerous functions: "eval(", "exec(", "system(", "shell_exec", "pickle.loads"
  - SQL queries: "SELECT", "INSERT", "UPDATE", "DELETE", "DROP"
  - Web vulnerabilities: "innerHTML", "dangerouslySetInnerHTML", "render_template_string"
  - File operations: "open(", "readfile", "writefile", "unlink"
- Use `graph://callers/{{qualified_name}}` to trace data flow from user input to sensitive functions
- Use `graph://callees/{{qualified_name}}` to identify calls to dangerous functions
- Use `index://status/{{repository}}` to ensure full codebase coverage

**For Each Finding, Provide**:

1. **Severity**: Critical, High, Medium, Low (use CVSS 3.1 scoring if applicable)
   - Critical: Immediate exploitation possible, data breach risk
   - High: Exploitable with effort, significant impact
   - Medium: Requires specific conditions, moderate impact
   - Low: Minor impact or theoretical vulnerability

2. **Location**: Specific file:line references

3. **Vulnerability Description**:
   - What's the vulnerability?
   - Why is it dangerous?
   - What data or functionality is at risk?

4. **Exploit Scenario** (if applicable):
   - How could an attacker exploit this?
   - What's the potential impact?
   - Example attack payload

5. **Remediation**:
   - How to fix the vulnerability
   - Secure code examples
   - Best practices to follow

6. **References**:
   - CWE number (e.g., CWE-89 for SQL Injection)
   - CVE numbers (if dependency vulnerability)
   - OWASP reference links

**Priority**: Focus on {scope_desc} vulnerabilities with potential for data breach, privilege escalation, or remote code execution.

Provide a comprehensive security assessment with actionable recommendations.
""".strip()

    # Log successful registration
    logger.info(
        "mcp.prompts.registered",
        prompts=6,
        names=[
            "analyze_codebase",
            "refactor_suggestions",
            "find_bugs",
            "generate_tests",
            "explain_code",
            "security_audit"
        ]
    )
