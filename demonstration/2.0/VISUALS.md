# MnemoLite v2.0 - Visual Assets Library

## Title Slide Visuals

### The Memory Palace (ASCII Art)
```
                    ╔═══════════════════════════════╗
                    ║     THE DIGITAL MEMORY        ║
                    ║           PALACE              ║
                    ╚════════════╤══════════════════╝
                                 │
                    ╔════════════╧══════════════╗
                    ║                            ║
         ╔══════════╬══════════╗    ╔══════════╬══════════╗
         ║     WEST WING       ║    ║     EAST WING        ║
         ║   Agent Memories    ║    ║   Code Intelligence  ║
         ║                     ║    ║                      ║
         ║  📚 Conversations   ║    ║  🔬 AST Analysis     ║
         ║  💭 Contexts        ║    ║  🕸️ Dependencies     ║
         ║  🔮 Embeddings      ║    ║  🎯 Dual Embeddings  ║
         ╚═════════════════════╝    ╚══════════════════════╝
                    │                            │
                    └────────────┬───────────────┘
                                 │
                         ╔═══════╧════════╗
                         ║ PostgreSQL 18  ║
                         ║  Foundation    ║
                         ╚════════════════╝
```

### The Curator's Badge
```
            ╭─────────────────╮
            │    CURATOR      │
            │  ═══════════    │
            │   MnemoLite     │
            │    v2.0.0       │
            ╰─────────────────╯
```

---

## Memory Flow Visualizations

### Memory Formation Animation
```
Frame 1:                    Frame 2:                    Frame 3:
User Input                  Processing                  Stored Memory
    │                          │                            │
    ▼                          ▼                            ▼
┌─────────┐               ┌─────────┐                ┌─────────┐
│ "Query" │               │ [......] │                │ ✓ #4267 │
└─────────┘               │ Encoding │                │ 0.768D  │
                          └─────────┘                └─────────┘
```

### Semantic Search Web
```
                     Query: "optimization"
                            ╱│╲
                          ╱  │  ╲
                        ╱    │    ╲
                      ╱      │      ╲
                    ▼        ▼        ▼
              [0.92]    [0.87]    [0.85]
              Memory    Memory    Memory
                #42       #17       #89
                 ╲        │        ╱
                   ╲      │      ╱
                     ╲    │    ╱
                       ╲  │  ╱
                         ╲│╱
                      Unified
                      Results
```

---

## Code Intelligence Diagrams

### AST Parsing Visualization
```
Source Code                AST                        Intelligence
───────────               ─────                      ─────────────

def calculate():          Function                   ┌──────────────┐
    data = get()          ├─ name: calculate        │ Functions: 3 │
    result = process()    ├─ body:                  │ Calls: 5     │
    return result         │  ├─ Assignment(data)    │ Complexity: 7│
                          │  ├─ Assignment(result)  │ Dependencies: │
                          │  └─ Return(result)      │  - get()      │
                          └─ calls:                 │  - process()  │
                             ├─ get()                └──────────────┘
                             └─ process()
```

### Dependency Graph Animation
```
Step 1: Start Point        Step 2: First Hop         Step 3: Full Graph

   calculate()                calculate()                 calculate()
       ?                          │                           │
                             ┌────┴────┐                ┌────┼────┐
                             ▼         ▼                ▼    ▼    ▼
                          get()    process()         get() proc() log()
                             ?         ?               │     │     │
                                                       ▼     ▼     ▼
                                                     db()  calc() file()
```

---

## Performance Visualizations

### Latency Comparison Chart
```
Operation               Latency Bar
─────────────────────────────────────────────────────
Vector Search      ████░░░░░░░░░░░░░░░░ 12ms
Hybrid Search      ███░░░░░░░░░░░░░░░░░ 11ms
Graph Traversal    ▏░░░░░░░░░░░░░░░░░░░ 0.155ms ⚡
Metadata Filter    █░░░░░░░░░░░░░░░░░░░ 3ms
Memory Creation    ██░░░░░░░░░░░░░░░░░░ 8ms
Code Indexing      ███████████░░░░░░░░░ 45ms

                   0ms                           50ms
```

### Throughput Gauge
```
     Embeddings/Second (CPU)
    ╭─────────────────────╮
    │ ░░░░░░░░░░████████ │
    │         75 emb/s    │
    ╰─────────────────────╯
    0                    100
```

---

## Architecture Diagrams

### System Layers (Clean Architecture)
```
         ╔═══════════════════════════════════╗
         ║          User Interface            ║
         ║        (HTMX 2.0 + FastAPI)        ║
         ╚═══════════════╤═══════════════════╝
                         │
         ╔═══════════════╧═══════════════════╗
         ║         Application Layer          ║
         ║    (Services & Orchestration)      ║
         ╚═══════════════╤═══════════════════╝
                         │
         ╔═══════════════╧═══════════════════╗
         ║          Domain Layer              ║
         ║     (Business Logic & Rules)       ║
         ╚═══════════════╤═══════════════════╝
                         │
         ╔═══════════════╧═══════════════════╗
         ║       Infrastructure Layer         ║
         ║    (PostgreSQL 18 + Extensions)    ║
         ╚═════════════════════════════════════╝
```

### Data Flow Pipeline
```
    Input                Processing            Storage             Retrieval
    ─────                ──────────           ───────             ─────────

    Code/Memory ──► Parse/Analyze ──► Embed ──► Store ──► Index
        │               │                │         │         │
        ▼               ▼                ▼         ▼         ▼
    ┌────────┐    ┌──────────┐    ┌────────┐ ┌──────┐ ┌────────┐
    │Raw Data│───►│AST/Meta  │───►│Vectors │─►│ PG18 │◄─│Search │
    └────────┘    └──────────┘    └────────┘ └──────┘ └────────┘
                        │                          │
                        ▼                          ▼
                  ┌──────────┐               ┌──────────┐
                  │Metadata  │               │Results   │
                  └──────────┘               └──────────┘
```

---

## Interactive Demo Screens

### Terminal Demo Layout
```
┌─────────────────────── Terminal ───────────────────────┐
│ $ curl -X POST http://localhost:8001/v1/events/        │
│   -H "Content-Type: application/json"                  │
│   -d '{"content": "User asked about optimization"}'    │
│                                                         │
│ Response:                                               │
│ {                                                       │
│   "id": "550e8400-e29b-41d4-a716-446655440000",      │
│   "timestamp": "2024-01-15T14:30:00Z",                │
│   "status": "stored",                                  │
│   "embedding_generated": true                          │
│ }                                                       │
│                                                         │
│ $ curl "http://localhost:8001/v1/search/?q=optimize"   │
│ {                                                       │
│   "data": [                                            │
│     {"content": "User asked about optimization",       │
│      "similarity": 0.92, "timestamp": "14:30:00"},    │
│     {"content": "Database query optimization tips",    │
│      "similarity": 0.87, "timestamp": "14:25:00"}     │
│   ]                                                    │
│ }                                                       │
└─────────────────────────────────────────────────────────┘
```

---

## Testing Pyramid Visual

### Animated Test Progress
```
                 Performance Tests
                      ╱─────╲
                     ╱   ✓   ╲
                    ╱─────────╲
                   ╱   UI Tests ╲
                  ╱      ✓✓✓    ╲
                 ╱───────────────╲
                ╱ Code Intelligence╲
               ╱      ✓✓✓✓✓✓      ╲
              ╱─────────────────────╲
             ╱   Agent Memory API    ╲
            ╱        ✓✓✓✓✓✓✓✓        ╲
           ╱───────────────────────────╲
          ╱      Smoke Tests           ╲
         ╱         ✓✓✓✓✓✓✓✓✓✓          ╲
        ╱───────────────────────────────╲
       ╱   Infrastructure Checks         ╲
      ╱          ✓✓✓✓✓✓✓✓                ╲
     ────────────────────────────────────────

     Progress: ████████████████████░ 95%
     Tests Passed: 40/42
```

---

## Docker Optimization Visual

### Before vs After
```
BEFORE (v1.3)                    AFTER (v2.0)
─────────────                    ────────────

Image Size:   2.2 GB             Image Size:   341 MB  (-84%)
Build Time:   5 min              Build Time:   20 sec  (-93%)
Context:      500 MB             Context:      13 MB   (-97%)

     ████████████████             ███░░░░░░░░
     ████████████████             ███░░░░░░░░
     ████████████████    ──►      ███░░░░░░░░
     ████████████████             ░░░░░░░░░░░
     ████████████████             ░░░░░░░░░░░
```

---

## Future Roadmap Timeline

### Visual Roadmap
```
2024 Timeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1 ████████████ Foundation Complete
   └─ Dual Architecture ✓
   └─ PostgreSQL 18 ✓
   └─ 245 Tests ✓

Q2 ░░░░████████ Scale & Optimize
   └─ Partitioning (500k)
   └─ INT8 Quantization
   └─ PGMQ Workers

Q3 ░░░░░░░░████ Intelligence Evolution
   └─ Multi-language AST
   └─ Cross-repo graphs
   └─ Pattern learning

Q4 ░░░░░░░░░░░░ The Cognitive Leap
   └─ Self-improving suggestions
   └─ Memory-aware generation
   └─ Semantic refactoring
```

---

## Closing Slide Art

### The Gift
```
           ╭────────────────────────────╮
           │                            │
           │   🏛️  YOUR PALACE AWAITS   │
           │                            │
           │  ┌──────────────────────┐  │
           │  │  West    ││    East  │  │
           │  │  Wing    ││    Wing  │  │
           │  │          ││          │  │
           │  │ MEMORIES ││   CODE   │  │
           │  └──────────┬───────────┘  │
           │             │              │
           │       PostgreSQL 18        │
           │                            │
           │    github.com/.../mnemo    │
           ╰────────────────────────────╯

         "Where Memory Meets Intelligence"
```

---

## Quick Reference Cards

### For Slides
```
┌─────────────────┐
│ Key Metrics     │
├─────────────────┤
│ • 12ms search   │
│ • 0.155ms graph │
│ • 768D vectors  │
│ • 50k+ scale    │
│ • 245 tests     │
└─────────────────┘
```

### For Demos
```
┌─────────────────┐
│ Demo Commands   │
├─────────────────┤
│ make up         │
│ make api-test   │
│ make logs       │
│ curl /health    │
│ curl /search    │
└─────────────────┘
```

---

## Emoji Legend (for slides)

- 🏛️ Architecture/Foundation
- 💭 Memory/Thoughts
- 🔬 Analysis/Code Intelligence
- 🕸️ Graph/Network
- ⚡ Performance/Speed
- 🎯 Target/Goal
- 🔮 Embedding/Vector
- 📚 Knowledge/Documentation
- 🛠️ Tools/Building
- ✨ Magic/Innovation
- 🚀 Future/Launch
- 🎭 Story/Narrative

---

## Color Scheme Suggestions

For slide templates:
- **Primary**: Deep Blue (#1e3a8a) - Trust, depth
- **Secondary**: Warm Gold (#fbbf24) - Knowledge, value
- **Accent**: Electric Purple (#8b5cf6) - Innovation
- **Success**: Emerald (#10b981) - Growth
- **Background**: Off-white (#fafaf9) or Deep charcoal (#1f2937)

---

## Slide Transition Effects

Suggested transitions (if using presentation software):
1. **Memory Palace Reveal**: Fade in from center
2. **Wing Exploration**: Slide from left (West) or right (East)
3. **Graph Building**: Appear node by node
4. **Performance Metrics**: Count up animation
5. **Architecture Layers**: Build from bottom up
6. **Future Timeline**: Scroll horizontally

---

## Notes for Visual Implementation

1. **Keep ASCII art simple** - Should render well in terminals
2. **Use box-drawing characters** - ╔ ╗ ╚ ╝ ═ ║ ├ ┤ ┬ ┴ ┼
3. **Progressive disclosure** - Start simple, add detail
4. **Consistent metaphors** - Palace, wings, curator throughout
5. **Interactive elements** - Highlight what can be clicked/explored
6. **Accessibility** - Ensure contrast, provide text alternatives

---

*These visuals support the narrative journey from visitor to curator of the Memory Palace*

