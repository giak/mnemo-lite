"""
Integration tests for EPIC-26: TypeScript/JavaScript Code Graph Support.

Tests the complete flow:
1. Code chunking → TypeScript/JavaScript chunks
2. Metadata extraction → imports + calls

Story 26.5: Testing & Validation

NOTE: These tests focus on the chunking + metadata extraction pipeline.
Database and graph construction tests are in separate files.
"""

import pytest

from services.code_chunking_service import CodeChunkingService
from services.metadata_extractor_service import MetadataExtractorService


@pytest.fixture
def metadata_service():
    """Create metadata extractor service."""
    return MetadataExtractorService()


@pytest.fixture
def chunking_service(metadata_service):
    """Create code chunking service with metadata extraction."""
    return CodeChunkingService(max_workers=4, metadata_service=metadata_service)


@pytest.mark.asyncio
async def test_typescript_metadata_extraction_integration(
    chunking_service,
    metadata_service
):
    """
    Test that TypeScript code is chunked and metadata is extracted.

    EPIC-26 Story 26.5: Validation test.
    """
    # Simple TypeScript code with imports and calls
    source_code = """
import { UserService } from './services/user.service'
import { Router } from '@angular/router'

export class UserComponent {
    constructor(
        private userService: UserService,
        private router: Router
    ) {}

    async loadUsers() {
        const users = await this.userService.getAll()
        this.displayUsers(users)
    }

    displayUsers(users: User[]) {
        console.log(users)
    }

    navigateToUser(userId: string) {
        this.router.navigate(['/users', userId])
    }
}
"""

    # Step 1: Chunk the TypeScript code
    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        file_path="components/user.component.ts",
        language="typescript",
        
    )

    # Should create chunks for the class and methods
    assert len(chunks) > 0, "Should create at least one chunk"

    # Step 2: Verify metadata extraction for each chunk
    found_imports = False
    found_calls = False

    for chunk in chunks:
        metadata = chunk.metadata

        # Check if imports were extracted
        if metadata and "imports" in metadata:
            imports = metadata["imports"]
            if len(imports) > 0:
                found_imports = True
                # Should find the import statements
                assert any('./services/user.service' in imp for imp in imports), \
                    f"Should extract UserService import, got: {imports}"
                assert any('@angular/router' in imp for imp in imports), \
                    f"Should extract Router import, got: {imports}"

        # Check if calls were extracted
        if metadata and "calls" in metadata:
            calls = metadata["calls"]
            if len(calls) > 0:
                found_calls = True
                # Should find method calls
                print(f"Chunk {chunk.name} calls: {calls}")

    assert found_imports, "Should extract imports from at least one chunk"
    assert found_calls, "Should extract calls from at least one chunk"


@pytest.mark.asyncio
async def test_typescript_simple_imports_extraction(
    chunking_service,
    metadata_service
):
    """
    Test simple import extraction from TypeScript code.

    EPIC-26 Story 26.1 validation.
    """
    source_code = """
import { MyClass, MyFunction } from './models'
import * as utils from 'lodash'
import React from 'react'

export class MyComponent {
    render() {
        return React.createElement('div')
    }
}
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        file_path="components/my.component.ts",
        language="typescript",
        
    )

    assert len(chunks) > 0

    # Get metadata from chunks
    all_imports = []
    for chunk in chunks:
        if chunk.metadata and "imports" in chunk.metadata:
            all_imports.extend(chunk.metadata["imports"])

    # Verify imports were extracted
    assert any('./models.MyClass' in imp for imp in all_imports), \
        f"Should extract named import MyClass, got: {all_imports}"
    assert any('./models.MyFunction' in imp for imp in all_imports), \
        f"Should extract named import MyFunction, got: {all_imports}"
    assert any('lodash' in imp for imp in all_imports), \
        f"Should extract namespace import lodash, got: {all_imports}"
    assert any('react' in imp for imp in all_imports), \
        f"Should extract default import react, got: {all_imports}"


@pytest.mark.asyncio
async def test_typescript_simple_calls_extraction(
    chunking_service,
    metadata_service
):
    """
    Test simple call extraction from TypeScript code.

    EPIC-26 Story 26.2 validation.
    """
    source_code = """
export class Calculator {
    add(a: number, b: number): number {
        return a + b
    }

    calculate(items: number[]): number {
        const sum = this.add(1, 2)
        const total = items.reduce((acc, val) => acc + val, 0)
        return this.multiply(sum, total)
    }

    multiply(a: number, b: number): number {
        return a * b
    }
}
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        file_path="services/calculator.service.ts",
        language="typescript",
        
    )

    assert len(chunks) > 0

    # Get metadata from chunks
    all_calls = []
    for chunk in chunks:
        if chunk.metadata and "calls" in chunk.metadata:
            all_calls.extend(chunk.metadata["calls"])

    # Should extract method calls
    print(f"All calls extracted: {all_calls}")

    # Should find some calls (this.add, items.reduce, this.multiply, etc.)
    assert len(all_calls) > 0, "Should extract at least some calls"


@pytest.mark.asyncio
async def test_javascript_esm_imports_extraction(
    chunking_service,
    metadata_service
):
    """
    Test JavaScript ESM import extraction.

    EPIC-26 Story 26.3 validation: JavaScript reuses TypeScript extractor.
    """
    source_code = """
import { createServer } from 'http'
import express from 'express'
import * as path from 'path'

export function startServer() {
    const app = express()
    const server = createServer(app)
    return server
}
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        file_path="server.js",
        language="javascript",  # JavaScript, not TypeScript
        
    )

    assert len(chunks) > 0

    # Get metadata from chunks
    all_imports = []
    for chunk in chunks:
        if chunk.metadata and "imports" in chunk.metadata:
            all_imports.extend(chunk.metadata["imports"])

    # Verify imports were extracted for JavaScript
    assert any('http' in imp for imp in all_imports), \
        f"Should extract named import from 'http', got: {all_imports}"
    assert any('express' in imp for imp in all_imports), \
        f"Should extract default import express, got: {all_imports}"
    assert any('path' in imp for imp in all_imports), \
        f"Should extract namespace import path, got: {all_imports}"


@pytest.mark.asyncio
async def test_typescript_metadata_structure(
    chunking_service,
    metadata_service
):
    """
    Test that TypeScript metadata has the expected structure.

    EPIC-26 Story 26.3 validation.
    """
    source_code = """
import { Service } from './service'

export class MyClass {
    doSomething() {
        const result = this.helper()
        return result
    }

    helper() {
        return 42
    }
}
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        file_path="class.ts",
        language="typescript",
        
    )

    assert len(chunks) > 0

    # Check metadata structure
    for chunk in chunks:
        assert chunk.metadata is not None, f"Chunk {chunk.name} should have metadata"

        # TypeScript metadata should have imports and calls
        assert "imports" in chunk.metadata, \
            f"Chunk {chunk.name} metadata should have 'imports' field"
        assert "calls" in chunk.metadata, \
            f"Chunk {chunk.name} metadata should have 'calls' field"

        # Verify types
        assert isinstance(chunk.metadata["imports"], list), \
            f"Chunk {chunk.name} imports should be a list"
        assert isinstance(chunk.metadata["calls"], list), \
            f"Chunk {chunk.name} calls should be a list"


@pytest.mark.asyncio
async def test_typescript_real_world_component(
    chunking_service,
    metadata_service
):
    """
    Test with a more realistic Angular component.

    EPIC-26 Story 26.5: Real-world validation.
    """
    source_code = """
import { Component, OnInit } from '@angular/core'
import { Router, ActivatedRoute } from '@angular/router'
import { Observable } from 'rxjs'
import { map, filter } from 'rxjs/operators'
import { UserService } from '../services/user.service'
import { User } from '../models/user.model'

@Component({
  selector: 'app-user-list',
  templateUrl: './user-list.component.html',
  styleUrls: ['./user-list.component.css']
})
export class UserListComponent implements OnInit {
  users$: Observable<User[]>

  constructor(
    private userService: UserService,
    private router: Router,
    private route: ActivatedRoute
  ) {}

  ngOnInit(): void {
    this.loadUsers()
    this.setupFilters()
  }

  loadUsers(): void {
    this.users$ = this.userService.getAll()
      .pipe(
        map(users => users.filter(u => u.active)),
        filter(users => users.length > 0)
      )
  }

  setupFilters(): void {
    this.route.queryParams.subscribe(params => {
      this.filterUsers(params.search)
    })
  }

  filterUsers(searchTerm: string): void {
    console.log('Filtering users:', searchTerm)
  }

  navigateToUser(userId: string): void {
    this.router.navigate(['/users', userId])
  }
}
"""

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        file_path="components/user-list.component.ts",
        language="typescript",
        
    )

    assert len(chunks) > 0, "Should create chunks from Angular component"

    # Collect all imports and calls
    all_imports = set()
    all_calls = set()

    for chunk in chunks:
        if chunk.metadata:
            if "imports" in chunk.metadata:
                all_imports.update(chunk.metadata["imports"])
            if "calls" in chunk.metadata:
                all_calls.update(chunk.metadata["calls"])

    # Verify key imports
    assert any('@angular/core' in imp for imp in all_imports), \
        "Should extract @angular/core imports"
    assert any('@angular/router' in imp for imp in all_imports), \
        "Should extract @angular/router imports"
    assert any('rxjs' in imp for imp in all_imports), \
        "Should extract rxjs imports"
    assert any('../services/user.service' in imp for imp in all_imports), \
        "Should extract UserService import"

    # Verify some calls were extracted
    print(f"\nExtracted {len(all_imports)} unique imports")
    print(f"Extracted {len(all_calls)} unique calls")
    print(f"Sample imports: {list(all_imports)[:5]}")
    print(f"Sample calls: {list(all_calls)[:5]}")

    assert len(all_calls) > 0, "Should extract method calls from component"
