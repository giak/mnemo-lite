# MnemoLite – Spécification API (Draft v0.1)

> **Objectif (Ω)** : Définir un contrat clair, versionné, testable et documenté pour intégrer MnemoLite à Expanse et à tout client externe.

---

## 1. Alternatives considérées (Φ)
| Approche | Description | Avantages | Inconvénients |
|----------|-------------|-----------|---------------|
| **A. REST + JSON (OpenAPI 3.1)** | Endpoints CRUD + recherche, spec auto-générée | Simple, écosystème large, outils (FastAPI) | Verbeux, overfetching potentiel |
| **B. REST + JSON (JSON:API 1.1)** | Conventions fortes (include, sparse fields) | Normalise pagination & liens, moins de bikeshedding | Learning curve, moins d’outils Python |
| **C. gRPC + Protobuf** | Services typés, streaming bi‑directionnel | Performances, contrats stricts, code‑gen multilang | Plus complexe, firewall/unary http2, UI à fournir |
| **D. GraphQL** | Schéma unique typé, requêtes flexibles | Sous‑sélection fine, introspection native | N+1 backend, cache plus dur, complexité DDOS |

> **Décision (Δ)** : **A. REST + JSON + OpenAPI 3.1** pour V1 (interop, FastAPI) + prévoir **gRPC** optionnel pour ingestion haute fréquence.

---

## 2. Design principes (Ξ)
1. **Stateless** : chaque requête contient tout contexte.
2. **Versionné** : Prefix `/v1/…`, entêtes `X-API-Version`.
3. **Predictable** codes HTTP (200/201/400/404/422/500).
4. **Consistent** : enveloppe réponse `{ "data":…, "meta":… }`.
5. **Observabilité** : trace‑id dans header `X-Trace-Id`, endpoint `/metrics` Prometheus.

---

## 3. Endpoints principaux (Λ)
| Méthode | Route | Fonction | Auth |
|---------|-------|----------|------|
| POST | `/v1/events` | Ingestion d’un événement | none (dev) |
| GET | `/v1/events/{id}` | Récupérer par UID | none |
| GET | `/v1/search` | Recherche vectorielle + filtres | none |
| POST | `/v1/psi/query` | Question réflexive (Ψ) | none |
| GET | `/v1/stats` | KPIs système (M) | none |
| GET | `/v1/healthz` | Liveness / readiness | none |

---

## 4. Spécification OpenAPI (extrait)
```yaml
openapi: 3.1.0
info:
  title: MnemoLite API
  version: 1.0.0
servers:
  - url: https://mnemo.local/api/v1
paths:
  /events:
    post:
      summary: Ingestion d’un événement
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/NewEvent'
      responses:
        '201':
          description: Événement créé
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Event'
  /events/{id}:
    get:
      summary: Détail d’un événement
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Event'
  /search:
    get:
      summary: Recherche multi‑critères
      parameters:
        - in: query
          name: q
          schema:
            type: string
        - in: query
          name: top_k
          schema:
            type: integer
            default: 10
      responses:
        '200':
          description: Résultats classés
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SearchResults'
components:
  schemas:
    NewEvent:
      type: object
      required: [timestamp, content]
      properties:
        timestamp:
          type: string
          format: date-time
        expiration:
          type: string
          format: date-time
        memory_type:
          type: string
        event_type:
          type: string
        role_id:
          type: integer
        content:
          type: object
        metadata:
          type: object
    Event:
      allOf:
        - $ref: '#/components/schemas/NewEvent'
        - type: object
          properties:
            id:
              type: string
              format: uuid
    SearchResults:
      type: object
      properties:
        data:
          type: array
          items:
            $ref: '#/components/schemas/Event'
        meta:
          type: object
          properties:
            query_time_ms:
              type: number
            top_k:
              type: integer
```

---

## 5. Gestion des erreurs
```json
{
  "error": {
    "code": "ValidationError",
    "message": "memory_type inconnu: WORKING",
    "details": { "field": "memory_type" }
  }
}
```
Codes typiques : **400** input, **404** non trouvé, **409** doublon, **422** schema, **500** interne.

---

## 6. Pagination, filtrage, tri
- **Pagination keyset** : `?after=<cursor>&limit=50`.
- **Tri** : `sort=-timestamp`.
- **Filtres** : `memory_type=episodic`, `role_id=2`.

---

## 7. Sécurité (future)
- Header `Authorization: Bearer <token>` (JWT HS256).
- Rôles : `viewer`, `editor`, `admin`.

---

## 8. KPI & Observabilité (M)
- `/metrics` exporte Prometheus (`mnemo_query_latency_seconds`).
- Header `X-Trace-Id` renvoyé miroir pour corrélation.

---

## 9. Prochaines étapes (Ψ)
1. Valider modèle yaml via `openapi-generator`.
2. Générer client Python/TS.
3. Intégrer tests `pytest` avec `fastapi.testclient` (coverage ≥ 90 %).
4. Brancher hooks CI pour changer version `info.version` sur tag Git.

