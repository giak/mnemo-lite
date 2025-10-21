# CLAUDE.md - MnemoLite (Compressed DSL)

**DSL:** §=section ◊=concept →=flow ⊕=compose ∧=AND !=critical @=loc |=OR {}=set :=def +=add ←=emph

v2.3.2 | 2025-10-21 | EPIC-06 (74pts) + EPIC-07 (41pts) + EPIC-08 (24pts) Complete | EPIC-10 (35pts) In Progress | EPIC-11 (13/13pts) COMPLETE ✅ | EPIC-12 (13/23pts - 57%) Stories 12.1, 12.2, 12.3 COMPLETE ✅

## §IDENTITY

MnemoLite: PG18.cognitive.memory ⊕ pgvector ⊕ pg_partman ⊕ pgmq ⊕ Redis ⊕ CODE.INTEL
Stack: FastAPI(0.111+) ⊕ SQLAlchemy(2.0+.async) ⊕ asyncpg ⊕ redis[hiredis] ⊕ sentence-transformers(2.7+) ⊕ tree-sitter ⊕ tembo-pgmq ⊕ structlog
UI: HTMX(1.9+) ⊕ Jinja2 ⊕ Cytoscape.js(3.28) ⊕ Chart.js(4.4) ⊕ SCADA.theme
Arch: PG18.only ∧ CQRS.inspired ∧ DIP.protocols ∧ async.first ∧ EXTEND>REBUILD ∧ L1+L2.cache

## §PRINCIPLES

◊Core: technical.objectivity ∧ factual ∧ challenge.assumptions → absolute.truth | ¬sycophancy

## §DEV.OPS

◊Start: make.{up, down, restart, build, logs, ps}
◊DB: make.db-{shell, backup, restore|file=X, create-test, fill-test, test-reset}
◊Test: make.api-{test, test-file|file=X, test-one|test=X, coverage}
! Tests: mnemolite_test @ TEST_DATABASE_URL (separate.db → avoid.dev.pollution) + EMBEDDING_MODE=mock
◊Dev: make.{api-shell, worker-shell, api-debug|file=X}
◊QA: make.{lint, lint-fix, health, benchmark}
◊Perf: ./apply_optimizations.sh {test|apply|benchmark|rollback} → 10s.rollback
◊Quick.Test: ./test_application.sh {quick|full|load} → passing

## §STRUCTURE

api/{
main.py:entry+lifespan+15.routes,
dependencies.py:DI,
db/{database, repositories/{base,event,memory,code*chunk,node,edge}},
interfaces/{repos,svcs}.Protocol,
models/{event,memory,embedding,code_chunk,graph}.pydantic,
routes/{event:v1, search:v1, health, code_indexing:v1, code_search:v1, code_graph:v1, ui_routes:15.endpoints},
services/{
embedding, search, processor, notification,
code_chunking, code_indexing, metadata_extractor, dual_embedding, symbol_path,
graph_construction, graph_traversal, hybrid_code_search, lexical_search, vector_search, rrf_fusion,
caches/{redis_cache}
},
utils/{timeout, circuit_breaker, circuit_breaker_registry},
config/{timeouts, circuit_breakers}
}
templates/{base, dashboard, search, graph, monitoring, code*{dashboard,repos,search,graph,upload}, partials/{event_list,code_results,repo_list}}
static/{css/{base,scada,navbar}, js/components/{graph,code_graph,filters,monitoring}}
db/{Dockerfile:PG18+pgvector+partman, init/{01-ext,01-init,02-partman}.sql}
tests/{conftest:fixtures, test\*\*\*{routes,service,repo}.py, db/repositories/test\_\*.py}
scripts/{generate_test_data, benchmarks/}

## §ARCH

◊Layers: routes → services → repositories → PG18
◊DI: interfaces/(Protocol) → dependencies.py → Depends() → routes
◊Repo: SQLAlchemy.Core.async @ api/db/repositories/
◊Services: business.logic → orchestrate.repos → Protocol.based
◊CQRS: Cmd(direct) | Query(routes→svcs→repos→PG18) | PGMQ:infra.ready
◊Engine: main.py.lifespan → app.state.db_engine → pool{20,overflow:10} → 100req/s.sustained
◊Cache: L1(CodeChunk:100MB.LRU.MD5) + L2(Redis:2GB.LRU.shared) → L3(PG18) → 3-tier.arch
◊Cache.TTL: {event:60s, search:30s, graph:120s} → 80%+.hit → 0ms.cached → graceful.degradation
◊Pipeline: 7.steps{parse→chunk→metadata→embed(dual)→store→graph→index} → <100ms/file
◊Robustness: timeouts + circuit.breakers + transactions → production.ready (EPIC-12)
◊Timeout.Config: utils/timeout.py + config/timeouts.py → 13.operations → env.var.override → <1ms.overhead
◊Circuit.Breakers: Redis(5,30s) + Embedding(3,60s) → fast.fail + auto.recovery → health.monitoring

## §TIMEOUTS (EPIC-12)

◊Philosophy: zero.tolerance.infinite.hangs → all.long.ops.time.limited → graceful.fallback
◊Implementation: asyncio.wait_for + with_timeout() → context.preservation → structured.logging
◊Config: centralized @ config/timeouts.py → env.vars{TIMEOUT_*} → runtime.tuning

◊Critical.Operations (5 services protected):
  tree_sitter_parse: 5s → fallback.fixed.chunking
  embedding_generation: {single:10s, batch:30s} → error.propagation
  graph_construction: 10s → error.propagation
  graph_traversal: 5s → <1ms.typical
  index_file: 60s → cumulative.pipeline.timeout

◊Usage.Patterns:
  Direct: await with_timeout(op(), timeout=get_timeout("op_name"), context={...})
  Decorator: @timeout_decorator(timeout=5.0, operation_name="my_op")
  Config: TIMEOUT_TREE_SITTER=10.0 docker compose up

! Fallback: code_chunking → fixed.chunking.on.timeout → never.fails
! Propagation: embedding/graph → TimeoutError.raised → caller.handles
! Overhead: <1ms.per.operation → negligible.P99.impact
! Tuning: set_timeout("op_name", 10.0) → dynamic.adjustment → reset_to_defaults()

## §CIRCUIT-BREAKERS (EPIC-12)

◊Philosophy: prevent.cascading.failures → fast.fail.when.broken → auto.recovery.attempts
◊Implementation: 3-state.machine (CLOSED→OPEN→HALF_OPEN) → utils/circuit_breaker.py (~400 lines)
◊Config: centralized @ config/circuit_breakers.py → env.vars{*_CIRCUIT_*} → per-service.tuning
◊Registry: circuit_breaker_registry.py → /health.endpoint.integration → observability

◊Protected.Services (2 external dependencies):
  Redis.Cache (L2): threshold=5, recovery=30s → graceful.L1→L3.cascade
  Embedding.Service: threshold=3, recovery=60s → auto.retry.after.OOM

◊State.Machine:
  CLOSED: normal.operation → record.failures → open.at.threshold
  OPEN: fail.fast(<1ms) → wait.recovery.timeout → transition.HALF_OPEN
  HALF_OPEN: test.recovery(1.call) → success=CLOSED | failure=OPEN

◊Usage.Patterns:
  Automatic: circuit_breaker.can_execute() → record_success() | record_failure()
  Decorator: @breaker.protect (async functions)
  Monitoring: GET /health → circuit_breakers{state,failure_count,config}

! Fast.Fail: Redis.down → <1ms.response (vs 5000ms.timeout) → 5000x.faster
! Auto.Recovery: Embedding.OOM → retry.after.60s → no.manual.restart
! Log.Reduction: Redis.outage → 99.9%.fewer.logs (1.per.30s vs 1000s/sec)
! Health.Degradation: critical_circuits_open=["embedding_service"] → 503.status

## §TRANSACTIONS (EPIC-12)

◊Philosophy: atomic.operations → zero.partial.failures → cache+db.consistency
◊Implementation: repository.connection.param → service.layer.transaction.wrappers
◊Pattern: async with engine.begin() as conn: repo.method(conn, ...) → rollback.on.error

◊Protected.Operations (3 repositories):
  code_chunk_repository: batch_insert + bulk_delete → atomic.multi-chunk
  node_repository: create + bulk_delete_by_repository → atomic.graph.ops
  edge_repository: create + bulk_delete_by_source_node → atomic.relationships

◊Service.Transactions:
  code_indexing_service.index_file() → chunks+embeddings.atomic
  graph_construction_service.build_graph() → nodes+edges.atomic
  code_indexing_routes.delete_repository() → chunks+nodes+edges+cache.atomic

! Backward.Compatible: connection.param.optional → existing.code.works
! Cache.Coordination: transaction.rollback → cache.invalidation → consistency
! Zero.Partial.Failures: all-or-nothing → clean.error.recovery

## §DB.SCHEMA

◊events: {id:UUID.PK, timestamp:TIMESTAMPTZ+Btree, content:JSONB, embedding:VECTOR(768)+HNSW(m:16,ef_construction:64), metadata:JSONB+GIN.jsonb_path_ops}
! Partitioning: POSTPONED→500k (overhead>benefit) → monitor:db/init/03-monitoring-views.sql → activate:db/scripts/enable_partitioning.sql
! Future: PK:(id,timestamp).composite + Vector.idx:per.partition.only

◊code_chunks: {id:UUID.PK, file_path:TEXT, language:TEXT, chunk_type:ENUM{function,class,method,module}, source_code:TEXT, name:TEXT, name_path:TEXT+Btree+trgm, start_line:INT, end_line:INT, embedding_text:VECTOR(768)+HNSW, embedding_code:VECTOR(768)+HNSW, metadata:JSONB+GIN, repository:TEXT, commit_hash:TEXT, indexed_at:TS}
! Dual.Embed: TEXT(nomic-embed-text-v1.5) + CODE(jina-embeddings-v2-base-code) → 768D.each → enables.hybrid.search
! EPIC-11: name_path=hierarchical.qualified.name (e.g., "models.user.User.validate") → enables.symbol.disambiguation
! No.Partitioning: code_chunks → monitor@1M+.chunks (unlikely.near.term)

◊nodes: {node_id:UUID.PK, node_type:{function,class,method}, label:TEXT, properties:JSONB{chunk_id,file_path,complexity,signature}, created_at:TS}
! Graph: chunk→node(1:1) → enables.dependency.graph

◊edges: {edge_id:UUID.PK, source_node_id:UUID, target_node_id:UUID, relation_type:{calls,imports}, properties:JSONB, created_at:TS} → NO.FK
! Resolution: local(same.file)→imports(tracked)→best_effort → complete.accuracy
! Builtins: Python.built-ins.filtered → clean.graph

◊Graph.Traversal: recursive.CTE → ≤3.hops → <1ms → ~100x.target

## §CODE.INTEL

◊Chunking: tree-sitter.AST → {function,class,method,module} → avg.7.chunks/file
◊Metadata: {complexity:cyclomatic, calls:resolved, imports:tracked, signature:extracted}
◊Search: hybrid{RRF(k=60)⊕lexical(BM25)⊕vector(cosine)} → <200ms
◊Symbol.Path: EPIC-11.hierarchical.qualified.names → "models.user.User.validate" → enables.disambiguation
! SymbolPathService: generate_name_path() + extract_parent_context() + multi-language.support
! Strict.Containment: < and > (not ≤ and ≥) → prevents.boundary.false.positives

## §UI

◊Stack: HTMX(1.9+) ⊕ Jinja2 ⊕ Cytoscape.js(graph) ⊕ Chart.js(analytics) ⊕ SCADA.theme
◊Pages: 5{dashboard:KPIs+charts, repos:manage, search:hybrid, graph:cytoscape, upload:drag-drop}
◊Routes: /ui/{/, search, graph, monitoring, code/{dashboard,repos,search,graph,upload}}
◊Theme: SCADA.dark{bg:#0a0e27, accent:blue/green/red/cyan, mono:SF-Mono}
◊Philosophy: EXTEND>REBUILD → copy.existing{graph.html→code_graph.html} → adapt.minimal → ~10x.faster
◊Performance: page.load:<100ms | HTMX.partial:<50ms | cytoscape.render:<200ms
! Pattern: templates/{main,partials/htmx} → static/js/components/{graph,code_graph,filters}

## §TEST

◊DB: mnemolite_test @ TEST_DATABASE_URL → reset:make.db-test-reset
◊Types: {route,service,repo,protocol}.tests
◊Framework: pytest-asyncio + @pytest.mark.anyio → conftest.py:fixtures{async.engine,test.client}
◊Coverage: ~87% (events) + complete (code_intel)

## §DOCKER

◊Services: db(mnemo-postgres:PG18), redis(mnemo-redis:7-alpine,2GB), api(mnemo-api:8001→8000,uvicorn --reload)
◊Volumes: {./api:/app, ./tests:/app/tests} → live.reload
◊ENV: {DATABASE_URL, TEST_DATABASE_URL←CRITICAL, REDIS_URL:redis://redis:6379/0, EMBEDDING_MODEL:nomic-ai/nomic-embed-text-v1.5, CODE_EMBEDDING_MODEL:jinaai/jina-embeddings-v2-base-code, EMBEDDING_DIMENSION:768, EMBEDDING_MODE:{real|mock}, ENVIRONMENT:{dev|test|prod}, API_PORT:8001, POSTGRES_PORT:5432}

## §API

v1/{events, search:hybrid(vec+meta+time), health, code/index:POST.files, code/search:{hybrid,lexical,vector}, code/graph:{build,traverse,path,stats}}
UI:{/, /search, /graph, /monitoring, /code/{dashboard,repos,search,graph,upload}}
Docs:http://localhost:8001/docs

## §PERF (local,~50k.events+14.code_chunks)

Events: Vector(HNSW):~12ms | Hybrid:~11ms (cached:~5ms,-88%) | Meta+time:~3ms
! EPIC-08: Throughput:10→100req/s(10x) | P99:~200ms(~50x) | Cache.hit:80%+
CodeIntel:
  Indexing:<100ms/file
  Search:{hybrid:<200ms, lexical:<50ms, vector:<100ms}
  Graph:{construction:<1ms, traversal:≤3.hops}
  Analytics:{dashboard:<50ms, KPIs:<20ms}
UI: page.load:<100ms | HTMX.partial:<50ms | cytoscape.render:<200ms

! Post-part: partition.pruning → faster
◊Optimize: {Partitioning:monitor→activate@500k, HNSW:tune{m,ef_construction,ef_search}, JSONB:jsonb_path_ops+@>, Vector:ALWAYS.limit, Cache:adjust.TTL.per.hit.rate}

## §LIFECYCLE

Now: single.table + FP32 + no.retention
Future@500k: {hot(0-12mo):FP32, warm(>12mo):INT8, retention:detach|delete}

## §GOTCHAS

! Partitioning: DISABLED→500k → PK:(id,ts).AFTER + Vector.idx:per.partition.AFTER + partition.pruning.auto
! Tests: TEST_DATABASE_URL.ALWAYS + EMBEDDING_MODE=mock → avoid.model.loading
! Async: all.db→async/await
! Protocols: new.repos/svcs→implement.Protocol
! JSONB: jsonb_path_ops>jsonb_ops
! Cache: L1(in-mem)+L2(Redis)+L3(PG18) → transparent → graceful.degradation
! Cache.L2: 2GB.Redis → LRU.eviction → shared.multi-instance → TTL{30s:search,120s:graph}
! Pool: 20.connections → sufficient.100req/s → prevent.timeouts

! CodeChunk.Embeddings: store.in.dict → BEFORE.CodeChunkCreate (embeddings.on.base.model:FAIL)
! GraphService.Method: build_graph_for_repository() NOT build_repository_graph() (method.name.matters!)
! SQL.Complexity: AVG(((metadata->>'complexity')::jsonb->>'cyclomatic')::float) (cast.order:CRITICAL)
! SQL.ColumnNames: properties NOT props, relation_type NOT relationship (schema.exact.match.required)
! UI.Philosophy: EXTEND>REBUILD → copy.existing → adapt.minimal → ~10x.faster
! Graph.Builtins: Python.builtins.filtered → avoid.graph.pollution → clean.dependencies
! Rollback: ./apply_optimizations.sh rollback → 10s.recovery → backups.automatic
! Cache.Stats: curl http://localhost:8001/v1/events/cache/stats | jq → monitor.hit.rate
! AsyncClient: use.ASGITransport(app) NOT app=app → pytest.fixture.compatibility
! DualEmbedding: MUST.use.EmbeddingDomain.HYBRID.for.code → NOT.TEXT.only → RAM:~2.5GB
! EPIC-11.ParentContext: reverse=True CRITICAL → outermost-to-innermost (not reversed!)
! EPIC-11.Containment: < and > (strict) NOT <= and >= → prevents.boundary.false.positives
! EPIC-11.Migration: v3→v4.sql adds name_path + 2.indexes (Btree+trgm) → backward.compatible

## §SKILLS

◊epic-manager: .claude/skills/epic-manager/ → EPIC.documentation.management{create, update, validate, sync.dashboard}
! Auto-invoked: Claude.detects("Create EPIC-X", "Sync dashboard", "Validate EPIC-X")
! Safety: {never.delete.EPICs, always.backup, preserve.completed.points}

## §REF

docs/{arch,bdd_schema,api_spec,docker,foundation,test_inv}.md
docs/agile/{EPIC-06_README.md:74pts, EPIC-07_README.md:41pts, EPIC-08_README.md:24pts}.complete + EPIC-09_Advanced_File_Upload_README.md:35pts.proposed
docs/agile/{EPIC-06_PHASE_4_STORY_6_COMPLETION_REPORT.md, EPIC-07_MVP_COMPLETION_REPORT.md, EPIC-08_COMPLETION_REPORT.md}
docs/agile/serena-evolution/03_EPICS/{EPIC-10_PERFORMANCE_CACHING.md, EPIC-10_STORY_10.1_COMPLETION_REPORT.md:8pts.complete, EPIC-10_STORY_10.2_COMPLETION_REPORT.md:8pts.complete}
docs/agile/serena-evolution/03_EPICS/{EPIC-11_SYMBOL_ENHANCEMENT.md:13/13pts.COMPLETE, EPIC-11_STORY_11.1_COMPLETION_REPORT.md:5pts, EPIC-11_STORY_11.2_COMPLETION_REPORT.md:3pts, EPIC-11_STORY_11.3_COMPLETION_REPORT.md:2pts, EPIC-11_STORY_11.4_COMPLETION_REPORT.md:3pts, EPIC-11_COMPREHENSIVE_AUDIT_REPORT.md:5.bugs.fixed}
docs/agile/serena-evolution/03_EPICS/{EPIC-12_README.md:13/23pts.57%, EPIC-12_ROBUSTNESS.md, EPIC-12_COMPREHENSIVE_ANALYSIS.md}
docs/agile/serena-evolution/03_EPICS/{EPIC-12_STORY_12.1_COMPLETION_REPORT.md:5pts.timeouts, EPIC-12_STORY_12.2_COMPLETION_REPORT.md:3pts.transactions, EPIC-12_STORY_12.3_COMPLETION_REPORT.md:5pts.circuit-breakers}
db/migrations/{v2_to_v3.sql:content_hash, v3_to_v4.sql:name_path+indexes, v4_to_v5_performance_indexes.sql:proposed}
docs/SERENA_COMPARISON_ANALYSIS.md → architecture.insights + 8.actionable.improvements
docs/SERENA_ULTRATHINK_AUDIT.md → 25+.patterns.cachés + 15+.optimisations.subtiles
tests/README.md | http://localhost:8001/docs
