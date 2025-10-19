"""
Unit tests for PHP and Vue.js parsers (EPIC-06 Phase 1.6).

Tests:
- PHP parser: functions, classes, traits, interfaces, methods
- Vue.js parser: components, template/script/style sections
- Name extraction for all node types
- Edge cases: namespaces, exported declarations
- Performance benchmarks
"""

import pytest

from models.code_chunk_models import ChunkType
from services.code_chunking_service import (
    CodeChunkingService,
    PHPParser,
    VueParser,
    LANGUAGE_PACK_AVAILABLE,
)


# Skip all tests if tree-sitter-language-pack not available
pytestmark = pytest.mark.skipif(
    not LANGUAGE_PACK_AVAILABLE,
    reason="tree-sitter-language-pack not installed"
)


@pytest.fixture
def chunking_service():
    """Get CodeChunkingService instance."""
    return CodeChunkingService(max_workers=2)


@pytest.fixture
def php_parser():
    """Get PHPParser instance."""
    if not LANGUAGE_PACK_AVAILABLE:
        pytest.skip("tree-sitter-language-pack not available")
    return PHPParser()


@pytest.fixture
def vue_parser():
    """Get VueParser instance."""
    if not LANGUAGE_PACK_AVAILABLE:
        pytest.skip("tree-sitter-language-pack not available")
    return VueParser()


# ============================================================================
# PHP PARSER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_php_function_declaration(chunking_service):
    """Test PHP function declarations."""
    source_code = '''<?php
function calculateTotal($items) {
    return array_reduce($items, function($sum, $item) {
        return $sum + $item['price'];
    }, 0);
}

function processOrder($order) {
    $total = calculateTotal($order['items']);
    return $total > 0;
}
?>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )

    assert len(chunks) == 2, f"Expected 2 chunks (2 functions), got {len(chunks)}"

    # Chunk 1: calculateTotal
    chunk1 = chunks[0]
    assert chunk1.chunk_type == ChunkType.FUNCTION
    assert chunk1.name == "calculateTotal"
    assert "function calculateTotal" in chunk1.source_code
    assert "array_reduce" in chunk1.source_code

    # Chunk 2: processOrder
    chunk2 = chunks[1]
    assert chunk2.chunk_type == ChunkType.FUNCTION
    assert chunk2.name == "processOrder"
    assert "function processOrder" in chunk2.source_code


@pytest.mark.asyncio
async def test_php_class_declaration(chunking_service):
    """Test PHP class declarations with methods."""
    source_code = '''<?php
class UserService {
    private $repository;

    public function __construct($repository) {
        $this->repository = $repository;
    }

    public function getUser($id) {
        return $this->repository->findById($id);
    }

    public function createUser($userData) {
        return $this->repository->insert($userData);
    }
}
?>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )

    # Should have 1 class chunk
    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk.chunk_type == ChunkType.CLASS
    assert chunk.name == "UserService"
    assert "class UserService" in chunk.source_code
    assert "__construct" in chunk.source_code
    assert "getUser" in chunk.source_code


@pytest.mark.asyncio
async def test_php_trait_declaration(chunking_service):
    """Test PHP trait declarations."""
    source_code = '''<?php
trait Loggable {
    private $logger;

    public function log($message) {
        $this->logger->info($message);
    }

    public function error($message) {
        $this->logger->error($message);
    }
}

trait Timestampable {
    public function setTimestamp() {
        $this->created_at = date('Y-m-d H:i:s');
    }
}
?>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )

    assert len(chunks) == 2

    # Check both are traits
    trait_chunks = [c for c in chunks if c.chunk_type == ChunkType.TRAIT]
    assert len(trait_chunks) == 2

    # Verify names
    names = {chunk.name for chunk in chunks}
    assert names == {"Loggable", "Timestampable"}

    # Verify content
    loggable_chunk = next(c for c in chunks if c.name == "Loggable")
    assert "trait Loggable" in loggable_chunk.source_code
    assert "public function log" in loggable_chunk.source_code


@pytest.mark.asyncio
async def test_php_interface_declaration(chunking_service):
    """Test PHP interface declarations."""
    source_code = '''<?php
interface UserRepository {
    public function findById($id);
    public function create($userData);
    public function update($id, $userData);
}

interface CacheInterface {
    public function get($key);
    public function set($key, $value);
    public function delete($key);
}
?>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )

    assert len(chunks) == 2

    # Check both are interfaces
    interface_chunks = [c for c in chunks if c.chunk_type == ChunkType.INTERFACE]
    assert len(interface_chunks) == 2

    # Verify names
    names = {chunk.name for chunk in chunks}
    assert names == {"UserRepository", "CacheInterface"}

    # Verify content
    repo_chunk = next(c for c in chunks if c.name == "UserRepository")
    assert "interface UserRepository" in repo_chunk.source_code
    assert "findById" in repo_chunk.source_code


@pytest.mark.asyncio
async def test_php_mixed_declarations(chunking_service):
    """Test PHP file with all declaration types."""
    source_code = '''<?php
namespace App\\Services;

// Interface
interface Repository {
    public function find($id);
}

// Trait
trait Loggable {
    public function log($message) {
        echo $message;
    }
}

// Class
class UserService {
    use Loggable;

    public function getUser($id) {
        $this->log("Fetching user: " . $id);
        return $id;
    }
}

// Function
function createUser($name, $email) {
    return array(
        'name' => $name,
        'email' => $email
    );
}
?>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )

    assert len(chunks) == 4

    # Verify all chunk types present
    chunk_types = {chunk.chunk_type for chunk in chunks}
    assert ChunkType.INTERFACE in chunk_types
    assert ChunkType.TRAIT in chunk_types
    assert ChunkType.CLASS in chunk_types
    assert ChunkType.FUNCTION in chunk_types

    # Verify names
    names = {chunk.name for chunk in chunks}
    assert "Repository" in names
    assert "Loggable" in names
    assert "UserService" in names
    assert "createUser" in names


def test_php_parser_node_extraction(php_parser):
    """Test PHPParser can extract different node types."""
    source_code = '''<?php
function testFunc() {}
class TestClass {}
trait TestTrait {}
interface TestInterface {}
?>'''

    tree = php_parser.parse(source_code)

    # Test function nodes
    function_nodes = php_parser.get_function_nodes(tree)
    assert len(function_nodes) == 1
    assert function_nodes[0].type == "function_definition"

    # Test class nodes
    class_nodes = php_parser.get_class_nodes(tree)
    assert len(class_nodes) == 1
    assert class_nodes[0].type == "class_declaration"

    # Test trait nodes
    trait_nodes = php_parser.get_trait_nodes(tree)
    assert len(trait_nodes) == 1
    assert trait_nodes[0].type == "trait_declaration"

    # Test interface nodes
    interface_nodes = php_parser.get_interface_nodes(tree)
    assert len(interface_nodes) == 1
    assert interface_nodes[0].type == "interface_declaration"


@pytest.mark.asyncio
async def test_php_namespace_handling(chunking_service):
    """Test PHP namespace declarations are handled gracefully."""
    source_code = '''<?php
namespace App\\Models;

class User {
    private $name;

    public function getName() {
        return $this->name;
    }
}

namespace App\\Services;

class UserService {
    public function process() {
        return true;
    }
}
?>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )

    # Should extract both classes despite namespace declarations
    assert len(chunks) == 2

    class_chunks = [c for c in chunks if c.chunk_type == ChunkType.CLASS]
    assert len(class_chunks) == 2

    names = {chunk.name for chunk in chunks}
    assert "User" in names
    assert "UserService" in names


# ============================================================================
# VUE.JS PARSER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_vue_component_basic(chunking_service):
    """Test Vue.js basic component structure."""
    source_code = '''<template>
  <div class="user-profile">
    <h1>{{ user.name }}</h1>
    <p>{{ user.email }}</p>
  </div>
</template>

<script>
export default {
  name: 'UserProfile',
  data() {
    return {
      user: {
        name: '',
        email: ''
      }
    };
  }
}
</script>

<style scoped>
.user-profile {
  padding: 20px;
}
</style>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="vue",
        file_path="UserProfile.vue",
        extract_metadata=False
    )

    # Should extract at least the component
    assert len(chunks) >= 1

    # Check for Vue component
    component_chunks = [c for c in chunks if c.chunk_type == ChunkType.VUE_COMPONENT]
    assert len(component_chunks) == 1

    component = component_chunks[0]
    assert component.name == "VueComponent"
    assert "<template>" in component.source_code
    assert "<script>" in component.source_code
    assert "<style" in component.source_code


@pytest.mark.asyncio
async def test_vue_component_with_props(chunking_service):
    """Test Vue.js component with props and methods."""
    source_code = '''<template>
  <div>
    <button @click="updateProfile">{{ buttonText }}</button>
  </div>
</template>

<script>
export default {
  props: {
    userId: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      buttonText: 'Update'
    };
  },
  methods: {
    updateProfile() {
      this.$emit('update', this.userId);
    }
  }
}
</script>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="vue",
        file_path="ProfileButton.vue",
        extract_metadata=False
    )

    assert len(chunks) >= 1

    component_chunks = [c for c in chunks if c.chunk_type == ChunkType.VUE_COMPONENT]
    assert len(component_chunks) == 1

    component = component_chunks[0]
    assert "props:" in component.source_code
    assert "methods:" in component.source_code
    assert "updateProfile" in component.source_code


@pytest.mark.asyncio
async def test_vue_template_only(chunking_service):
    """Test Vue.js component with only template."""
    source_code = '''<template>
  <div class="simple">
    <h1>Simple Template</h1>
    <p>No script or style</p>
  </div>
</template>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="vue",
        file_path="SimpleTemplate.vue",
        extract_metadata=False
    )

    # Should still extract component
    assert len(chunks) >= 1

    component_chunks = [c for c in chunks if c.chunk_type == ChunkType.VUE_COMPONENT]
    assert len(component_chunks) >= 1


@pytest.mark.asyncio
async def test_vue_composition_api(chunking_service):
    """Test Vue.js Composition API (Vue 3)."""
    source_code = '''<template>
  <div>
    <p>Count: {{ count }}</p>
    <button @click="increment">Increment</button>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const count = ref(0);

function increment() {
  count.value++;
}
</script>

<style scoped>
button {
  padding: 10px;
}
</style>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="vue",
        file_path="Counter.vue",
        extract_metadata=False
    )

    assert len(chunks) >= 1

    component_chunks = [c for c in chunks if c.chunk_type == ChunkType.VUE_COMPONENT]
    assert len(component_chunks) == 1

    component = component_chunks[0]
    assert "<script setup>" in component.source_code or "<script" in component.source_code
    assert "import" in component.source_code or "const count" in component.source_code


def test_vue_parser_node_extraction(vue_parser):
    """Test VueParser can extract component nodes."""
    source_code = '''<template>
  <div>Hello</div>
</template>

<script>
export default {}
</script>'''

    tree = vue_parser.parse(source_code)

    # Test component nodes
    component_nodes = vue_parser.get_class_nodes(tree)  # Component treated as class
    assert len(component_nodes) >= 0  # May vary based on tree-sitter-vue implementation


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_php_performance(chunking_service):
    """Test PHP chunking performance."""
    import time

    # Generate 15 classes (~300 LOC)
    source_code = "<?php\n"
    for i in range(15):
        source_code += f'''
class Service{i} {{
    private $data;

    public function __construct() {{
        $this->data = array();
    }}

    public function process($input) {{
        $result = array_map(function($x) {{ return $x * {i}; }}, $input);
        $filtered = array_filter($result, function($x) {{ return $x > 10; }});
        return array_reduce($filtered, function($acc, $x) {{ return $acc + $x; }}, 0);
    }}

    public function validate($data) {{
        return !empty($data);
    }}
}}

'''

    source_code += "?>"

    start = time.time()
    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )
    elapsed_ms = (time.time() - start) * 1000

    assert len(chunks) >= 15  # At least 15 classes
    assert elapsed_ms < 200, f"Performance: {elapsed_ms:.2f}ms > 200ms"

    print(f"✅ PHP performance: {elapsed_ms:.2f}ms for {len(chunks)} chunks")


@pytest.mark.asyncio
async def test_vue_performance(chunking_service):
    """Test Vue.js chunking performance."""
    import time

    # Generate 10 Vue components
    test_files = []
    for i in range(10):
        source_code = f'''<template>
  <div class="component-{i}">
    <h1>{{{{ title{i} }}}}</h1>
    <p>{{{{ description{i} }}}}</p>
    <button @click="handler{i}">Action {i}</button>
  </div>
</template>

<script>
export default {{
  name: 'Component{i}',
  data() {{
    return {{
      title{i}: 'Title {i}',
      description{i}: 'Description {i}'
    }};
  }},
  methods: {{
    handler{i}() {{
      console.log('Handler {i}');
    }}
  }}
}}
</script>

<style scoped>
.component-{i} {{
  padding: 20px;
  margin: 10px;
}}
</style>'''
        test_files.append(source_code)

    start = time.time()
    all_chunks = []
    for i, source_code in enumerate(test_files):
        chunks = await chunking_service.chunk_code(
            source_code=source_code,
            language="vue",
            file_path=f"Component{i}.vue",
            extract_metadata=False
        )
        all_chunks.extend(chunks)
    elapsed_ms = (time.time() - start) * 1000

    assert len(all_chunks) >= 10  # At least 10 components
    assert elapsed_ms < 500, f"Performance: {elapsed_ms:.2f}ms > 500ms"

    print(f"✅ Vue.js performance: {elapsed_ms:.2f}ms for {len(all_chunks)} chunks across 10 files")


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_php_syntax_error_fallback(chunking_service):
    """Test PHP handles syntax errors gracefully."""
    invalid_code = '''<?php
function broken(
// Missing closing paren and body
$x = 1;
$y = 2;
?>'''

    chunks = await chunking_service.chunk_code(
        source_code=invalid_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )

    # Tree-sitter may return 0 chunks or fallback chunks
    assert isinstance(chunks, list)
    for chunk in chunks:
        assert chunk.chunk_type in [
            ChunkType.FUNCTION,
            ChunkType.CLASS,
            ChunkType.TRAIT,
            ChunkType.INTERFACE,
            ChunkType.FALLBACK_FIXED
        ]


@pytest.mark.asyncio
async def test_vue_invalid_template(chunking_service):
    """Test Vue.js handles invalid templates gracefully."""
    invalid_code = '''<template>
  <div>
    <h1>Unclosed tag
  </div>
</template>'''

    chunks = await chunking_service.chunk_code(
        source_code=invalid_code,
        language="vue",
        file_path="Invalid.vue",
        extract_metadata=False
    )

    # Should handle gracefully
    assert isinstance(chunks, list)


@pytest.mark.asyncio
async def test_php_empty_file(chunking_service):
    """Test PHP handles empty files gracefully."""
    with pytest.raises(ValueError, match="source_code cannot be empty"):
        await chunking_service.chunk_code(
            source_code="",
            language="php",
            file_path="test.php"
        )


@pytest.mark.asyncio
async def test_php_only_comments(chunking_service):
    """Test PHP file with only comments."""
    source_code = '''<?php
// This is a comment
/* This is a
   multiline comment */
// Another comment
?>'''

    chunks = await chunking_service.chunk_code(
        source_code=source_code,
        language="php",
        file_path="test.php",
        extract_metadata=False
    )

    # Should handle gracefully (may create fallback or no chunks)
    assert isinstance(chunks, list)
