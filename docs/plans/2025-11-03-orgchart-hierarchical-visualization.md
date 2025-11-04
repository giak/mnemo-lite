# Orgchart Hierarchical Visualization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform orgchart from filtered import-only view to full hierarchical visualization showing Package → Module → File → Class/Function structure with semantic zoom.

**Architecture:** Add "contains" edge type to represent structural hierarchy (Package contains Module, Module contains File, File contains Class/Function). Frontend builds tree from "contains" edges and displays dependency edges ("imports", "calls", "re_exports") as secondary visual relationships. Semantic zoom filters nodes at all levels while preserving tree structure.

**Tech Stack:** Python (FastAPI backend), TypeScript/Vue3 (frontend), PostgreSQL (graph storage), G6 (graph visualization)

---

## Task 1: Backend - Add "contains" Edge Type Support

**Files:**
- Modify: `api/services/graph_construction_service.py:233-238` (add to edges_by_type)
- Modify: `api/models/graph_models.py` (document edge types)
- Test: `api/tests/services/test_graph_construction_service.py`

**Step 1: Write test for contains edge generation**

```python
# In api/tests/services/test_graph_construction_service.py
async def test_generate_contains_edges_for_hierarchy():
    """Test that contains edges are generated for structural hierarchy."""
    service = GraphConstructionService()

    # Create mock nodes representing hierarchy
    package_node = NodeModel(
        node_id=uuid.uuid4(),
        label="core",
        node_type="Package",
        repository_id=uuid.uuid4()
    )

    module_node = NodeModel(
        node_id=uuid.uuid4(),
        label="cv",
        node_type="Module",
        repository_id=package_node.repository_id,
        metadata={"parent_package": "core"}
    )

    # Generate contains edges
    edges = await service._generate_contains_edges([package_node, module_node])

    # Assert
    assert len(edges) == 1
    assert edges[0].relationship == "contains"
    assert edges[0].source_node == package_node.node_id
    assert edges[0].target_node == module_node.node_id
```

**Step 2: Run test to verify it fails**

Run: `pytest api/tests/services/test_graph_construction_service.py::test_generate_contains_edges_for_hierarchy -v`

Expected: FAIL with "AttributeError: 'GraphConstructionService' object has no attribute '_generate_contains_edges'"

**Step 3: Add contains edge type to metrics**

```python
# In api/services/graph_construction_service.py:233-238
# Modify the edges_by_type dictionary
edges_by_type = {
    "calls": len(call_edges),
    "imports": len(import_edges),
    "re_exports": len(reexport_edges),
    "contains": len(contains_edges),  # ADD THIS LINE
}
```

**Step 4: Implement _generate_contains_edges method**

```python
# In api/services/graph_construction_service.py, add after _create_reexport_edges method

async def _generate_contains_edges(
    self,
    nodes: List[NodeModel]
) -> List[EdgeModel]:
    """
    Generate 'contains' edges to represent structural hierarchy.

    Hierarchy levels:
    - Package contains Module
    - Module contains File
    - File contains Class/Function

    Args:
        nodes: All nodes in the graph

    Returns:
        List of EdgeModel with relationship="contains"
    """
    edges: List[EdgeModel] = []

    # Group nodes by type for efficient lookup
    nodes_by_type: Dict[str, List[NodeModel]] = {}
    for node in nodes:
        if node.node_type not in nodes_by_type:
            nodes_by_type[node.node_type] = []
        nodes_by_type[node.node_type].append(node)

    # Create Package → Module edges
    packages = nodes_by_type.get("Package", [])
    modules = nodes_by_type.get("Module", [])

    for module in modules:
        parent_package = module.metadata.get("parent_package") if module.metadata else None
        if parent_package:
            # Find matching package by label
            package = next((p for p in packages if p.label == parent_package), None)
            if package:
                edges.append(EdgeModel(
                    source_node=package.node_id,
                    target_node=module.node_id,
                    relationship="contains",
                    metadata={"hierarchy_level": "package_to_module"}
                ))

    # Create Module → File edges
    files = nodes_by_type.get("File", [])

    for file_node in files:
        parent_module = file_node.metadata.get("parent_module") if file_node.metadata else None
        if parent_module:
            module = next((m for m in modules if m.label == parent_module), None)
            if module:
                edges.append(EdgeModel(
                    source_node=module.node_id,
                    target_node=file_node.node_id,
                    relationship="contains",
                    metadata={"hierarchy_level": "module_to_file"}
                ))

    # Create File → Class/Function edges
    classes = nodes_by_type.get("Class", [])
    functions = nodes_by_type.get("Function", [])
    methods = nodes_by_type.get("Method", [])

    for entity in classes + functions + methods:
        parent_file = entity.file_path
        if parent_file:
            # Find file node by file_path
            file_node = next((f for f in files if f.file_path == parent_file), None)
            if file_node:
                edges.append(EdgeModel(
                    source_node=file_node.node_id,
                    target_node=entity.node_id,
                    relationship="contains",
                    metadata={"hierarchy_level": "file_to_entity"}
                ))

    return edges
```

**Step 5: Update build_graph to call _generate_contains_edges**

```python
# In api/services/graph_construction_service.py, in build_graph method
# After line 238 (edges_by_type), add:

# Generate structural hierarchy edges
logger.info("Generating structural hierarchy (contains edges)...")
contains_edges = await self._generate_contains_edges(nodes)
edges.extend(contains_edges)

# Update metrics
edges_by_type["contains"] = len(contains_edges)
```

**Step 6: Run test to verify it passes**

Run: `pytest api/tests/services/test_graph_construction_service.py::test_generate_contains_edges_for_hierarchy -v`

Expected: PASS

**Step 7: Commit**

```bash
git add api/services/graph_construction_service.py api/tests/services/test_graph_construction_service.py
git commit -m "feat(backend): add contains edge type for structural hierarchy

- Add _generate_contains_edges method to generate hierarchy edges
- Support Package→Module, Module→File, File→Entity relationships
- Add contains edge count to metrics"
```

---

## Task 2: Backend - Infer Parent Metadata During Indexation

**Files:**
- Modify: `api/services/graph_construction_service.py:470-500` (_create_node_from_chunk)
- Test: `api/tests/services/test_graph_construction_service.py`

**Step 1: Write test for parent metadata inference**

```python
# In api/tests/services/test_graph_construction_service.py
async def test_infer_parent_metadata_from_file_path():
    """Test that parent relationships are inferred from file_path."""
    service = GraphConstructionService()

    # Create mock chunk with structured file path
    chunk = ChunkModel(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        file_path="packages/core/src/cv/application/services/validation.service.ts",
        chunk_type="class",
        content="class BaseValidationService {}",
        metadata={}
    )

    # Create node
    node = await service._create_node_from_chunk(chunk, repo_name="code_test")

    # Assert parent metadata inferred
    assert node.metadata.get("parent_module") == "cv"
    assert node.metadata.get("parent_package") == "core"
    assert node.node_type == "Class"
```

**Step 2: Run test to verify it fails**

Run: `pytest api/tests/services/test_graph_construction_service.py::test_infer_parent_metadata_from_file_path -v`

Expected: FAIL with assertion error on parent_module

**Step 3: Add _infer_hierarchy_metadata helper method**

```python
# In api/services/graph_construction_service.py, add before _create_node_from_chunk

def _infer_hierarchy_metadata(self, file_path: str, chunk_type: str) -> Dict[str, Any]:
    """
    Infer parent package and module from file path.

    Expected patterns:
    - packages/{package}/src/{module}/...
    - src/{module}/...
    - {module}/...

    Args:
        file_path: Full file path
        chunk_type: Type of chunk (for determining node type)

    Returns:
        Dictionary with parent_package, parent_module, parent_folder
    """
    metadata: Dict[str, Any] = {}

    if not file_path:
        return metadata

    parts = file_path.split('/')

    # Try to find package (after "packages/")
    try:
        packages_idx = parts.index("packages")
        if packages_idx + 1 < len(parts):
            metadata["parent_package"] = parts[packages_idx + 1]
    except ValueError:
        pass

    # Try to find module (after "src/" or "packages/{pkg}/src/")
    try:
        src_idx = parts.index("src")
        if src_idx + 1 < len(parts):
            metadata["parent_module"] = parts[src_idx + 1]
    except ValueError:
        # Fallback: use first directory as module
        if len(parts) > 1:
            metadata["parent_module"] = parts[0]

    # Store parent folder for file-level entities
    if chunk_type in ["class", "function", "method"]:
        # Get directory containing the file
        metadata["parent_folder"] = '/'.join(parts[:-1])

    return metadata
```

**Step 4: Update _create_node_from_chunk to use inference**

```python
# In api/services/graph_construction_service.py:470-500
# Modify _create_node_from_chunk to call _infer_hierarchy_metadata

async def _create_node_from_chunk(
    self,
    chunk: ChunkModel,
    repo_name: str
) -> NodeModel:
    """Create a node from a chunk with inferred hierarchy metadata."""

    # Determine node type
    node_type = self._chunk_type_to_node_type(chunk.chunk_type)

    # Infer hierarchy metadata from file path
    hierarchy_metadata = self._infer_hierarchy_metadata(chunk.file_path, chunk.chunk_type)

    # Merge with existing metadata
    combined_metadata = {**(chunk.metadata or {}), **hierarchy_metadata}

    # Extract properties
    properties = {
        "chunk_id": str(chunk.id),
        "file_path": chunk.file_path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "language": chunk.language,
    }

    # Add barrel file indicator
    if chunk.chunk_type == "barrel":
        properties["is_barrel"] = True
        properties["re_exports"] = chunk.metadata.get("re_exports", [])
    else:
        properties["is_barrel"] = False

    return NodeModel(
        node_id=uuid.uuid4(),
        label=chunk.chunk_name or "Unknown",
        node_type=node_type,
        repository_id=chunk.repository_id,
        metadata=combined_metadata,
        properties=properties,
    )
```

**Step 5: Run test to verify it passes**

Run: `pytest api/tests/services/test_graph_construction_service.py::test_infer_parent_metadata_from_file_path -v`

Expected: PASS

**Step 6: Commit**

```bash
git add api/services/graph_construction_service.py api/tests/services/test_graph_construction_service.py
git commit -m "feat(backend): infer parent hierarchy from file paths

- Add _infer_hierarchy_metadata to extract parent_package and parent_module
- Support packages/{pkg}/src/{module} pattern
- Automatically populate hierarchy metadata during node creation"
```

---

## Task 3: Backend - Create Virtual Package/Module Nodes

**Files:**
- Modify: `api/services/graph_construction_service.py` (add _create_virtual_hierarchy_nodes)
- Test: `api/tests/services/test_graph_construction_service.py`

**Step 1: Write test for virtual node creation**

```python
# In api/tests/services/test_graph_construction_service.py
async def test_create_virtual_package_and_module_nodes():
    """Test creation of virtual Package and Module nodes."""
    service = GraphConstructionService()

    # Create mock file nodes with parent metadata
    file_nodes = [
        NodeModel(
            node_id=uuid.uuid4(),
            label="validation.service.ts",
            node_type="File",
            repository_id=uuid.uuid4(),
            metadata={"parent_package": "core", "parent_module": "cv"}
        ),
        NodeModel(
            node_id=uuid.uuid4(),
            label="user.service.ts",
            node_type="File",
            repository_id=uuid.uuid4(),
            metadata={"parent_package": "core", "parent_module": "user"}
        )
    ]

    # Create virtual nodes
    virtual_nodes = await service._create_virtual_hierarchy_nodes(file_nodes)

    # Assert: Should create 1 Package (core) and 2 Modules (cv, user)
    packages = [n for n in virtual_nodes if n.node_type == "Package"]
    modules = [n for n in virtual_nodes if n.node_type == "Module"]

    assert len(packages) == 1
    assert packages[0].label == "core"
    assert len(modules) == 2
    assert set(m.label for m in modules) == {"cv", "user"}
```

**Step 2: Run test to verify it fails**

Run: `pytest api/tests/services/test_graph_construction_service.py::test_create_virtual_package_and_module_nodes -v`

Expected: FAIL with "AttributeError: '_create_virtual_hierarchy_nodes'"

**Step 3: Implement _create_virtual_hierarchy_nodes method**

```python
# In api/services/graph_construction_service.py, add after _generate_contains_edges

async def _create_virtual_hierarchy_nodes(
    self,
    nodes: List[NodeModel]
) -> List[NodeModel]:
    """
    Create virtual Package and Module nodes based on metadata from existing nodes.

    Only creates virtual nodes if they don't already exist.

    Args:
        nodes: Existing nodes with parent metadata

    Returns:
        List of new virtual Package and Module nodes
    """
    virtual_nodes: List[NodeModel] = []

    # Track existing packages and modules
    existing_labels_by_type: Dict[str, Set[str]] = {
        "Package": set(),
        "Module": set(),
    }

    for node in nodes:
        if node.node_type in existing_labels_by_type:
            existing_labels_by_type[node.node_type].add(node.label)

    # Collect unique package and module names from metadata
    packages_to_create: Set[str] = set()
    modules_to_create: Set[str] = set()

    for node in nodes:
        if not node.metadata:
            continue

        parent_package = node.metadata.get("parent_package")
        if parent_package and parent_package not in existing_labels_by_type["Package"]:
            packages_to_create.add(parent_package)

        parent_module = node.metadata.get("parent_module")
        if parent_module and parent_module not in existing_labels_by_type["Module"]:
            modules_to_create.add(parent_module)

    # Create virtual Package nodes
    repository_id = nodes[0].repository_id if nodes else uuid.uuid4()

    for package_name in packages_to_create:
        virtual_nodes.append(NodeModel(
            node_id=uuid.uuid4(),
            label=package_name,
            node_type="Package",
            repository_id=repository_id,
            metadata={"is_virtual": True},
            properties={"created_from": "hierarchy_inference"}
        ))

    # Create virtual Module nodes
    for module_name in modules_to_create:
        # Try to determine parent package for this module
        parent_package = None
        for node in nodes:
            if node.metadata and node.metadata.get("parent_module") == module_name:
                parent_package = node.metadata.get("parent_package")
                break

        virtual_nodes.append(NodeModel(
            node_id=uuid.uuid4(),
            label=module_name,
            node_type="Module",
            repository_id=repository_id,
            metadata={
                "is_virtual": True,
                "parent_package": parent_package
            },
            properties={"created_from": "hierarchy_inference"}
        ))

    return virtual_nodes
```

**Step 4: Update build_graph to create virtual nodes**

```python
# In api/services/graph_construction_service.py, in build_graph method
# After creating all nodes from chunks, before generating edges:

# Create virtual Package/Module nodes for hierarchy
logger.info("Creating virtual hierarchy nodes...")
virtual_nodes = await self._create_virtual_hierarchy_nodes(nodes)
nodes.extend(virtual_nodes)
logger.info(f"Created {len(virtual_nodes)} virtual hierarchy nodes")
```

**Step 5: Run test to verify it passes**

Run: `pytest api/tests/services/test_graph_construction_service.py::test_create_virtual_package_and_module_nodes -v`

Expected: PASS

**Step 6: Run full test suite**

Run: `pytest api/tests/services/test_graph_construction_service.py -v`

Expected: All tests PASS

**Step 7: Commit**

```bash
git add api/services/graph_construction_service.py api/tests/services/test_graph_construction_service.py
git commit -m "feat(backend): create virtual Package and Module nodes

- Add _create_virtual_hierarchy_nodes to generate missing hierarchy nodes
- Create virtual nodes only if they don't exist
- Support multi-package monorepo structure"
```

---

## Task 4: Frontend - Remove Import Filter and Use All Edges

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:99-101`
- Test: Manual verification via browser

**Step 1: Remove the import-only filter**

```typescript
// In frontend/src/components/OrgchartGraph.vue:99-101
// REMOVE these lines:
// const importEdges = props.edges.filter(e => e.type === 'imports')
// console.log('[Orgchart] Import edges:', importEdges.length)

// REPLACE with:
const allEdges = props.edges
console.log('[Orgchart] All edges by type:',
  props.edges.reduce((acc, e) => {
    acc[e.type] = (acc[e.type] || 0) + 1
    return acc
  }, {} as Record<string, number>)
)
```

**Step 2: Update childrenMap to use all edges**

```typescript
// In frontend/src/components/OrgchartGraph.vue:186-194
// Change the comment and keep the logic but clarify purpose

// Build parent-child relationships from ALL edges
// For orgchart hierarchy, we'll use "contains" edges primarily
// Other edge types (imports, calls, re_exports) shown as secondary relationships
props.edges.forEach(edge => {
  // Only include edge if BOTH source and target are in filtered nodes
  if (filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)) {
    if (!childrenMap.has(edge.source)) {
      childrenMap.set(edge.source, [])
    }
    childrenMap.get(edge.source)!.push(edge.target)
  }
})
```

**Step 3: Test in browser**

1. Start frontend: `cd frontend && npm run dev`
2. Navigate to: `http://localhost:3000/orgchart`
3. Select repository: `code_test_clean`
4. Verify in console logs:
   - `[Orgchart] All edges by type:` shows counts for each type
   - `[Orgchart] Nodes appearing in edges:` should show higher number than before

Expected: More nodes visible (not just 38/500)

**Step 4: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue
git commit -m "fix(frontend): use all edge types for orgchart construction

- Remove filter limiting to 'imports' edges only
- Build tree from all available edges (contains, imports, calls, re_exports)
- Increase node coverage from 7.6% to full graph"
```

---

## Task 5: Frontend - Prioritize "contains" Edges for Tree Building

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:136-175` (buildTree function)
- Test: Manual verification via browser

**Step 1: Separate contains edges from dependency edges**

```typescript
// In frontend/src/components/OrgchartGraph.vue, after line 100
// Add edge separation logic

// Separate structural hierarchy edges from dependency edges
const containsEdges = props.edges.filter(e => e.type === 'contains')
const dependencyEdges = props.edges.filter(e => ['imports', 'calls', 're_exports'].includes(e.type))

console.log('[Orgchart] Contains edges (hierarchy):', containsEdges.length)
console.log('[Orgchart] Dependency edges:', dependencyEdges.length)
```

**Step 2: Build tree primarily from contains edges**

```typescript
// In frontend/src/components/OrgchartGraph.vue:182-194
// Modify childrenMap building to prioritize contains edges

const childrenMap = new Map<string, string[]>()

// FIRST: Build hierarchy from contains edges
containsEdges.forEach(edge => {
  if (filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)) {
    if (!childrenMap.has(edge.source)) {
      childrenMap.set(edge.source, [])
    }
    childrenMap.get(edge.source)!.push(edge.target)
  }
})

// Store dependency edges separately for visualization
const dependencyEdgeSet = new Set<string>()
dependencyEdges.forEach(edge => {
  if (filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)) {
    dependencyEdgeSet.add(`${edge.source}-${edge.target}`)
  }
})

console.log('[Orgchart] Hierarchy edges in childrenMap:',
  Array.from(childrenMap.entries()).reduce((sum, [_, children]) => sum + children.length, 0))
console.log('[Orgchart] Dependency edges (for secondary display):', dependencyEdgeSet.size)
```

**Step 3: Update buildTree to start from Package nodes**

```typescript
// In frontend/src/components/OrgchartGraph.vue:136-175
// Modify buildTree function to prioritize Package nodes as roots

const buildTree = () => {
  // Start with Package nodes as top-level roots
  const packageNodes = filteredNodes.filter(n => n.type === 'Package')

  if (packageNodes.length > 0) {
    console.log('[Orgchart] Found Package roots:', packageNodes.map(p => p.label))
    return packageNodes
  }

  // Fallback: Start with Module nodes
  const moduleNodes = filteredNodes.filter(n => n.type === 'Module')
  if (moduleNodes.length > 0) {
    console.log('[Orgchart] Found Module roots:', moduleNodes.map(m => m.label))
    return moduleNodes
  }

  // Fallback: Use existing module detection logic (entryPointIds)
  const roots = filteredNodes.filter(n => entryPointIds.has(n.id))

  if (roots.length === 0) {
    console.log('[Orgchart] No packages or modules found, finding most connected nodes...')

    // Use most connected nodes as roots (existing logic)
    const connectionCounts = new Map<string, number>()
    containsEdges.forEach(e => {
      connectionCounts.set(e.source, (connectionCounts.get(e.source) || 0) + 1)
    })

    const sorted = Array.from(connectionCounts.entries()).sort((a, b) => b[1] - a[1])
    const topRootId = sorted[0]?.[0]
    if (topRootId) {
      const topRoot = filteredNodes.find(n => n.id === topRootId)
      if (topRoot) {
        console.log('[Orgchart] Using top connected node as root:', topRoot.label)
        return [topRoot]
      }
    }

    console.log('[Orgchart] Falling back to first node')
    return filteredNodes.slice(0, 1)
  }

  console.log('[Orgchart] Found entry point roots:', roots.map(r => r.label))
  return roots
}
```

**Step 4: Test in browser**

1. Reload: `http://localhost:3000/orgchart`
2. Select: `code_test_clean`
3. Check console logs:
   - Should see Package nodes as roots
   - Higher tree coverage
4. Verify visual: Tree should show package structure

**Step 5: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue
git commit -m "feat(frontend): build orgchart tree from contains edges

- Separate contains edges (hierarchy) from dependency edges
- Prioritize Package nodes as tree roots
- Build hierarchical tree structure from contains relationships"
```

---

## Task 6: Frontend - Display Dependency Edges as Secondary Relationships

**Files:**
- Modify: `frontend/src/components/OrgchartGraph.vue:434-441` (edge styling)
- Test: Manual verification via browser

**Step 1: Add dependency edges to graph visualization**

```typescript
// In frontend/src/components/OrgchartGraph.vue:362-388
// Modify flattenTree to include dependency edges

const flattenTree = (node: any, nodes: any[] = [], edges: any[] = []) => {
  nodes.push({
    id: node.id,
    data: node.data
  })

  // Add hierarchical children edges (from tree structure)
  if (node.children) {
    node.children.forEach((child: any) => {
      edges.push({
        id: `${node.id}-${child.id}`,
        source: node.id,
        target: child.id,
        data: { type: 'hierarchy' }  // Mark as hierarchy edge
      })
      flattenTree(child, nodes, edges)
    })
  }

  return { nodes, edges }
}

const flatData = flattenTree(treeData)

// ADD: Include dependency edges as secondary relationships
dependencyEdges.forEach(edge => {
  // Only add if both nodes are in the tree
  const sourceInTree = flatData.nodes.some(n => n.id === edge.source)
  const targetInTree = flatData.nodes.some(n => n.id === edge.target)

  if (sourceInTree && targetInTree && filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)) {
    flatData.edges.push({
      id: `dep-${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      data: { type: edge.type }  // imports, calls, or re_exports
    })
  }
})

console.log('[Orgchart] Flattened data:', {
  nodes: flatData.nodes.length,
  hierarchyEdges: flatData.edges.filter(e => e.data?.type === 'hierarchy').length,
  dependencyEdges: flatData.edges.filter(e => e.data?.type !== 'hierarchy').length
})
```

**Step 2: Style hierarchy vs dependency edges differently**

```typescript
// In frontend/src/components/OrgchartGraph.vue:434-441
// Replace edge config with conditional styling

edge: {
  type: 'line',
  style: (data: any) => {
    const edgeType = data.data?.type

    if (edgeType === 'hierarchy') {
      // Solid line for structural hierarchy (contains)
      return {
        stroke: '#64748b',
        lineWidth: 2,
        endArrow: true,
        lineDash: undefined
      }
    } else {
      // Dashed line for dependencies (imports, calls, re_exports)
      const typeColors: Record<string, string> = {
        imports: '#3b82f6',    // Blue
        calls: '#10b981',      // Green
        re_exports: '#f59e0b'  // Amber
      }

      return {
        stroke: typeColors[edgeType] || '#94a3b8',
        lineWidth: 1.5,
        endArrow: true,
        lineDash: [4, 4],  // Dashed
        opacity: 0.6
      }
    }
  }
}
```

**Step 3: Test in browser**

1. Reload: `http://localhost:3000/orgchart`
2. Verify:
   - Solid lines show hierarchy (Package → Module → File)
   - Dashed colored lines show dependencies
   - Different colors for imports/calls/re_exports

**Step 4: Commit**

```bash
git add frontend/src/components/OrgchartGraph.vue
git commit -m "feat(frontend): display dependency edges as secondary relationships

- Add dependency edges (imports, calls, re_exports) to visualization
- Style hierarchy edges as solid lines
- Style dependency edges as dashed colored lines
- Use different colors per dependency type"
```

---

## Task 7: Integration Testing and Verification

**Files:**
- Test: Manual end-to-end testing
- Document: `docs/plans/2025-11-03-orgchart-hierarchical-visualization.md` (this file)

**Step 1: Reindex code_test repository**

```bash
# From MnemoLite root
cd /home/giak/Work/MnemoLite

# Reindex to generate contains edges
python /home/giak/Work/MnemoLite/scripts/index_directory.py \
  --directory /home/giak/Work/MnemoLite/code_test \
  --repository-name code_test_clean
```

Expected output: Should show "contains" edges in the indexation summary

**Step 2: Verify backend changes**

```bash
# Run backend tests
cd /home/giak/Work/MnemoLite/api
pytest tests/services/test_graph_construction_service.py -v

# Check graph endpoint returns contains edges
curl http://localhost:8000/code-graph/code_test_clean | jq '.edges[] | select(.type == "contains") | .type' | head -5
```

Expected: Tests pass, curl shows "contains" edges

**Step 3: Verify frontend rendering**

1. Open: `http://localhost:3000/orgchart`
2. Select: `code_test_clean`
3. Set zoom: 100%
4. Verify structure:
   - Root: Package node (e.g., "core")
   - Level 2: Module nodes (e.g., "cv", "user", "export")
   - Level 3: File/Class/Function nodes
5. Verify edges:
   - Solid lines show containment
   - Dashed lines show dependencies
6. Test zoom:
   - Reduce zoom to 50%
   - Verify leaf nodes disappear
   - Verify tree structure maintained

**Step 4: Test with CVgenerator (original problem repository)**

```bash
# Reindex CVgenerator if needed
python /home/giak/Work/MnemoLite/scripts/index_directory.py \
  --directory /path/to/CVgenerator \
  --repository-name CVgenerator
```

1. Select: `CVgenerator`
2. Verify: Should show all 500 nodes at 100% zoom
3. Verify: Hierarchical structure visible
4. Verify: No more "38/500" coverage issue

**Step 5: Document test results**

Add to this file (end of document):

```markdown
## Test Results

**Date:** [Fill in date]
**Tester:** [Your name]

### code_test_clean
- ✅ Shows Package → Module → File hierarchy
- ✅ Solid hierarchy edges visible
- ✅ Dashed dependency edges visible
- ✅ Zoom filtering works (50% → 100%)
- ✅ All nodes visible at 100%

### CVgenerator
- ✅ Shows all 500 nodes at 100% (was 38/500)
- ✅ Hierarchical structure clear
- ✅ Tree coverage: [X%]
- ✅ Performance: [acceptable/slow]

### Issues Found
[List any issues]

### Notes
[Any additional observations]
```

**Step 6: Final commit**

```bash
git add docs/plans/2025-11-03-orgchart-hierarchical-visualization.md
git commit -m "docs: add test results for orgchart hierarchical visualization"
```

---

## Task 8: Documentation and Cleanup

**Files:**
- Create: `docs/technical/orgchart-architecture.md`
- Update: `frontend/src/components/OrgchartGraph.vue` (add comprehensive comments)

**Step 1: Document the architecture**

```bash
# Create architecture documentation
touch docs/technical/orgchart-architecture.md
```

Content:

```markdown
# Orgchart Hierarchical Visualization Architecture

## Overview

The orgchart visualization displays code structure as a hierarchical tree with semantic zoom filtering.

## Hierarchy Levels

```
Repository
└── Package (e.g., core, shared, ui)
    └── Module (e.g., cv, user, export)
        └── File (e.g., validation.service.ts)
            └── Entity (Class, Function, Method)
```

## Edge Types

### Structural Hierarchy (Solid Lines)

- **`contains`**: Parent → Child relationship in code structure
  - Package contains Module
  - Module contains File
  - File contains Class/Function
  - Used to build the tree structure

### Dependencies (Dashed Lines)

- **`imports`**: File A imports File B (blue)
- **`calls`**: Function A calls Function B (green)
- **`re_exports`**: Barrel file re-exports symbol (amber)
- Shown as secondary relationships overlaid on tree

## Data Flow

### Backend (graph_construction_service.py)

1. **Index chunks** → Create nodes from code entities
2. **Infer hierarchy** → Add parent_package, parent_module to metadata
3. **Create virtual nodes** → Generate missing Package/Module nodes
4. **Generate edges**:
   - Contains edges from hierarchy metadata
   - Dependency edges from imports/calls/re-exports
5. **Return graph** → Nodes + all edge types

### Frontend (OrgchartGraph.vue)

1. **Receive graph data** → nodes[] + edges[]
2. **Filter by zoom** → Apply semantic scoring
3. **Separate edge types**:
   - containsEdges → Build tree structure
   - dependencyEdges → Overlay on tree
4. **Build tree** → Start from Package roots, traverse contains edges
5. **Render**:
   - Nodes with G6 dagre layout
   - Hierarchy edges as solid lines
   - Dependency edges as dashed colored lines

## Semantic Zoom

- **Input**: Zoom level 0-100%
- **Process**: Score each node by complexity + LOC + connections
- **Output**: Filter nodes to show top X% by score
- **Tree preservation**: If parent filtered out, orphan children become new roots

## Performance Considerations

- Virtual nodes added lazily (only missing ones)
- Dependency edges filtered to only show edges between visible nodes
- Tree traversal uses visited set to prevent cycles
- G6 handles layout optimization

## Future Enhancements

- Collapse/expand subtrees
- Focus mode (highlight single package/module)
- Edge filtering controls (show/hide by type)
- Search and highlight nodes
- Export to SVG/PNG
```

**Step 2: Add comprehensive component comments**

```typescript
// In frontend/src/components/OrgchartGraph.vue, at the top of <script setup>

/**
 * Organizational Chart Visualization using G6 CompactBox Layout
 *
 * Displays code hierarchy from packages down through imports, showing both
 * structural containment (solid edges) and dependency relationships (dashed edges).
 *
 * ARCHITECTURE:
 * - Tree structure built from "contains" edges (Package → Module → File → Entity)
 * - Dependency edges (imports, calls, re_exports) overlaid as secondary relationships
 * - Semantic zoom filters nodes while preserving tree structure
 *
 * EDGE TYPES:
 * - contains (solid): Structural hierarchy - defines tree structure
 * - imports (dashed blue): Import dependencies
 * - calls (dashed green): Function call dependencies
 * - re_exports (dashed amber): Re-export relationships
 *
 * PROPS:
 * - nodes: All graph nodes (Package, Module, File, Class, Function, etc.)
 * - edges: All graph edges (contains + dependency types)
 * - zoomLevel: 0-100, controls semantic filtering (100 = show all)
 * - weights: Scoring weights for semantic zoom (complexity, LOC, connections)
 * - viewMode: Visual encoding mode (hierarchy, complexity, hubs)
 */
```

**Step 3: Commit documentation**

```bash
git add docs/technical/orgchart-architecture.md frontend/src/components/OrgchartGraph.vue
git commit -m "docs: add orgchart hierarchical visualization architecture

- Document hierarchy levels and edge types
- Explain data flow backend → frontend
- Add semantic zoom details
- Add comprehensive component comments"
```

---

## Verification Checklist

Before considering this task complete, verify:

- [ ] Backend generates "contains" edges for all hierarchy levels
- [ ] Backend infers parent_package and parent_module from file paths
- [ ] Backend creates virtual Package/Module nodes when missing
- [ ] Frontend builds tree from contains edges
- [ ] Frontend displays dependency edges as dashed lines
- [ ] Semantic zoom works at all levels (0% to 100%)
- [ ] Tree structure preserved when filtering
- [ ] All 500 nodes visible at 100% zoom (CVgenerator test)
- [ ] Performance acceptable with large graphs (1000+ nodes)
- [ ] Documentation complete and accurate

## Known Limitations

1. **Cycle handling**: Contains edges should form a DAG; cycles not explicitly prevented
2. **Performance**: Large graphs (5000+ nodes) may be slow
3. **Layout**: G6 dagre layout may not be optimal for very wide trees
4. **Virtual nodes**: May create duplicates if indexation runs multiple times

## Future Enhancements

1. **Interactive filtering**: Click to collapse/expand subtrees
2. **Search**: Highlight and focus on specific nodes
3. **Edge filtering UI**: Toggle visibility by edge type
4. **Alternative layouts**: Support force-directed or radial layouts
5. **Export**: Save visualization as SVG or PNG
6. **Performance**: Virtualization for extremely large graphs (10k+ nodes)

---

## Test Results

*[To be filled in during Task 7]*
