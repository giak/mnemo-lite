# EPIC-24: Monitoring & Reliability ULTRATHINK

**Date**: 29 octobre 2025
**Criticité**: MAXIMALE (perte de données si échec)
**Objectif**: Système de surveillance infaillible pour le daemon auto-save

---

## 🎯 Problématique

**Situation Actuelle**:
- Daemon auto-save fonctionne (2241 conversations sauvegardées)
- Mais si daemon crash → **PERTE SILENCIEUSE de conversations**
- Aucun monitoring, aucune alerte, aucun auto-recovery

**Risques Identifiés**:
1. **Daemon crash silencieux** → conversations perdues à jamais
2. **API down** → daemon continue mais fail à sauvegarder
3. **DB connection loss** → import échoue sans alerte
4. **Disk full** → logs remplissent `/tmp`, crash
5. **Memory leak** → daemon consomme toute la RAM
6. **Parsing error** → transcripts corrompus bloquent import

**Conséquence**: PERTE IRRÉVERSIBLE de contexte historique

---

## 🏗️ Architecture de Surveillance Multi-Couches

### Layer 1: Daemon Self-Monitoring (Internal)

**Heartbeat File**
```bash
# Dans le daemon, écrire un heartbeat toutes les 30s
echo "$(date +%s)" > /tmp/daemon-heartbeat.txt

# Format heartbeat file:
{
  "last_beat": 1698576000,
  "last_import_success": 1698575970,
  "last_import_count": 3,
  "consecutive_failures": 0,
  "total_imported": 2241,
  "uptime_seconds": 3600
}
```

**Metrics File**
```bash
# Écrire métriques après chaque poll
/tmp/daemon-metrics.json:
{
  "timestamp": "2025-10-29T13:51:08Z",
  "status": "healthy",
  "last_poll": "2025-10-29T13:51:08Z",
  "last_success": "2025-10-29T12:50:37Z",
  "total_imported": 2241,
  "consecutive_failures": 0,
  "api_response_time_ms": 234,
  "memory_usage_mb": 45,
  "cpu_usage_percent": 2.1
}
```

---

### Layer 2: External Watchdog (Monitoring Script)

**Script**: `scripts/daemon-watchdog.sh`

```bash
#!/bin/bash
# Watchdog externe qui surveille le daemon
# Tourne en parallèle, vérifie heartbeat, auto-restart si dead

CHECK_INTERVAL=60  # Check every 60s
MAX_HEARTBEAT_AGE=120  # Alert if heartbeat > 2 minutes old
RESTART_THRESHOLD=3  # Restart after 3 consecutive failures

while true; do
    # 1. Check heartbeat file
    if [ -f /tmp/daemon-heartbeat.txt ]; then
        LAST_BEAT=$(cat /tmp/daemon-heartbeat.txt)
        NOW=$(date +%s)
        AGE=$((NOW - LAST_BEAT))

        if [ $AGE -gt $MAX_HEARTBEAT_AGE ]; then
            echo "[WATCHDOG] ALERT: Daemon heartbeat stale (${AGE}s old)"
            # Send alert + restart daemon
            restart_daemon
        fi
    else
        echo "[WATCHDOG] ALERT: Heartbeat file missing!"
        restart_daemon
    fi

    # 2. Check if daemon process exists
    if ! pgrep -f "conversation-auto-import.sh" > /dev/null; then
        echo "[WATCHDOG] ALERT: Daemon process not found!"
        restart_daemon
    fi

    # 3. Check API health
    if ! curl -s -f http://localhost:8000/health > /dev/null; then
        echo "[WATCHDOG] WARNING: API unhealthy"
    fi

    # 4. Check DB connection
    if ! docker compose exec -T db psql -U mnemo -d mnemolite -c "SELECT 1;" > /dev/null 2>&1; then
        echo "[WATCHDOG] WARNING: DB connection lost"
    fi

    # 5. Check disk space
    DISK_USAGE=$(df /tmp | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$DISK_USAGE" -gt 90 ]; then
        echo "[WATCHDOG] ALERT: Disk usage ${DISK_USAGE}%"
    fi

    sleep $CHECK_INTERVAL
done

restart_daemon() {
    echo "[WATCHDOG] Restarting daemon..."
    pkill -f conversation-auto-import.sh
    nohup bash /app/scripts/conversation-auto-import.sh > /tmp/daemon.log 2>&1 &
    echo "[WATCHDOG] Daemon restarted"
}
```

---

### Layer 3: API Health Endpoint

**Endpoint**: `GET /v1/autosave/health`

```python
@router.get("/health")
async def daemon_health_check(
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Health check complet du système auto-save.
    Retourne 200 si OK, 503 si critical issues.
    """
    issues = []
    status = "healthy"

    # 1. Check daemon heartbeat
    heartbeat_file = Path("/tmp/daemon-heartbeat.txt")
    if heartbeat_file.exists():
        last_beat = int(heartbeat_file.read_text().strip())
        age = time.time() - last_beat
        if age > 120:  # 2 minutes
            issues.append(f"Daemon heartbeat stale ({age}s)")
            status = "unhealthy"
    else:
        issues.append("Daemon heartbeat file missing")
        status = "critical"

    # 2. Check recent imports
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT MAX(created_at) FROM memories WHERE author = 'AutoImport'
        """))
        last_import = result.scalar()

        if last_import:
            age = datetime.now() - last_import.replace(tzinfo=None)
            if age.total_seconds() > 600:  # 10 minutes
                issues.append(f"No imports in last {age.total_seconds()}s")
                status = "degraded"

    # 3. Check metrics file
    metrics_file = Path("/tmp/daemon-metrics.json")
    if metrics_file.exists():
        metrics = json.loads(metrics_file.read_text())

        if metrics.get("consecutive_failures", 0) > 5:
            issues.append(f"High failure rate: {metrics['consecutive_failures']}")
            status = "degraded"

    # 4. Response
    response = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "daemon": {
            "heartbeat_age_seconds": age if 'age' in locals() else None,
            "last_import_at": last_import.isoformat() if last_import else None
        },
        "issues": issues
    }

    if status == "critical":
        raise HTTPException(status_code=503, detail=response)

    return response
```

---

### Layer 4: Docker Health Check

**docker-compose.yml**:

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "sh", "-c", "curl -f http://localhost:8000/health && curl -f http://localhost:8000/v1/autosave/health"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 120s

    # Auto-restart si unhealthy
    restart: unless-stopped
```

---

### Layer 5: Prometheus Metrics

**Exposition métriques Prometheus**:

```python
# api/routes/autosave_monitoring_routes.py

from prometheus_client import Counter, Gauge, Histogram

# Métriques
conversations_imported_total = Counter(
    'mnemolite_conversations_imported_total',
    'Total conversations imported'
)

daemon_heartbeat_age = Gauge(
    'mnemolite_daemon_heartbeat_age_seconds',
    'Age of daemon heartbeat in seconds'
)

import_duration_seconds = Histogram(
    'mnemolite_import_duration_seconds',
    'Time spent importing conversations'
)

@router.get("/metrics")
async def prometheus_metrics():
    """Expose Prometheus metrics"""
    return Response(
        content=generate_latest(),
        media_type="text/plain"
    )
```

---

### Layer 6: Alerting System

**Option 1: Script Email (Simple)**

```bash
# scripts/send-alert.sh
#!/bin/bash
SUBJECT="[ALERT] MnemoLite Auto-Save Daemon Issue"
TO="admin@example.com"
MESSAGE=$1

echo "$MESSAGE" | mail -s "$SUBJECT" "$TO"
```

**Option 2: Webhook Discord/Slack (Meilleur)**

```bash
# scripts/send-alert.sh
#!/bin/bash
WEBHOOK_URL="${DISCORD_WEBHOOK_URL}"
MESSAGE=$1

curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d "{\"content\": \"🚨 **MnemoLite Alert**: $MESSAGE\"}"
```

**Option 3: Prometheus Alertmanager (Production)**

```yaml
# alertmanager.yml
route:
  receiver: 'discord'

receivers:
  - name: 'discord'
    webhook_configs:
      - url: 'https://discord.com/api/webhooks/...'

# prometheus.yml
groups:
  - name: mnemolite
    interval: 60s
    rules:
      - alert: DaemonHeartbeatStale
        expr: mnemolite_daemon_heartbeat_age_seconds > 120
        for: 2m
        annotations:
          summary: "Daemon heartbeat is stale"

      - alert: NoRecentImports
        expr: time() - mnemolite_last_import_timestamp > 600
        for: 5m
        annotations:
          summary: "No imports in last 10 minutes"
```

---

## 🛠️ Implémentation Recommandée (3 Phases)

### Phase 1: Monitoring Basique (1h - IMMÉDIAT)

**Fichiers à créer**:
1. ✅ `scripts/daemon-watchdog.sh` - Watchdog externe
2. ✅ `api/routes/autosave_monitoring_routes.py` - Health endpoint
3. ✅ Modifier `scripts/conversation-auto-import.sh` - Ajouter heartbeat

**Modifications docker-compose.yml**:
```yaml
command:
  - sh
  - -c
  - |
    # Lancer daemon avec heartbeat
    nohup bash /app/scripts/conversation-auto-import.sh > /tmp/daemon.log 2>&1 &

    # Lancer watchdog en parallèle
    nohup bash /app/scripts/daemon-watchdog.sh > /tmp/watchdog.log 2>&1 &

    # Lancer API
    exec uvicorn main:app --host 0.0.0.0 --port 8000
```

**Tests**:
```bash
# 1. Vérifier heartbeat
docker compose exec api cat /tmp/daemon-heartbeat.txt

# 2. Vérifier health endpoint
curl http://localhost:8001/v1/autosave/health | jq

# 3. Simuler crash daemon
docker compose exec api pkill -f conversation-auto-import.sh
sleep 120  # Attendre watchdog (60s check + 60s grace)
docker compose exec api ps aux | grep conversation  # Doit être restarté
```

---

### Phase 2: Alerting & Dashboard (2h)

**Fichiers à créer**:
1. ✅ `scripts/send-alert.sh` - Script alertes Discord/Slack
2. ✅ `templates/monitoring_daemon.html` - Dashboard dédié daemon
3. ✅ `api/routes/autosave_monitoring_routes.py` - Endpoints stats

**Dashboard Features**:
- Graph timeline imports (Chart.js)
- Daemon status (heartbeat, uptime)
- Alert history (dernières 100 alertes)
- Métriques temps réel (poll rate, success rate)
- Button "Force Restart Daemon" (admin)

---

### Phase 3: Prometheus + Grafana (4h - OPTIONNEL)

**Stack complète**:
```yaml
# docker-compose.yml
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

**Dashboards Grafana**:
- Conversations imported over time
- Daemon uptime
- API response times
- Failure rate
- Disk/memory usage

---

## 🎯 Décision: Quelle Phase Implémenter?

### Recommandation: **Phase 1 (Immédiat) + Phase 2 (Sous 1 semaine)**

**Pourquoi?**
- ✅ Phase 1: Watchdog couvre 95% des risques critiques (1h effort)
- ✅ Phase 2: Dashboard + alertes pour visibilité (2h effort)
- ⚠️ Phase 3: Overkill pour projet solo (4h effort, complexité++)

**Phase 1 suffit si**:
- Tu checks `/v1/autosave/health` 1x par jour
- Tu as Discord/Slack pour recevoir alertes
- Tu acceptes restart automatique sans visibilité temps réel

**Phase 2 nécessaire si**:
- Tu veux dashboard visuel
- Tu veux historique des alertes
- Tu veux métriques détaillées (graphs)

**Phase 3 seulement si**:
- Équipe multi-users
- SLA strict (99.9% uptime)
- Budget monitoring infra

---

## 📋 Checklist Phase 1 (Action Immédiate)

- [ ] Modifier `conversation-auto-import.sh` → Ajouter heartbeat
- [ ] Créer `daemon-watchdog.sh` → Watchdog externe
- [ ] Créer endpoint `GET /v1/autosave/health` → Health check
- [ ] Modifier `docker-compose.yml` → Lancer watchdog
- [ ] Créer `send-alert.sh` → Notifications Discord/Slack
- [ ] Tester crash daemon + auto-restart
- [ ] Tester alerte si heartbeat stale
- [ ] Documenter monitoring dans README

**ETA Phase 1**: 1 heure
**ETA Tests**: 30 minutes
**Total**: 1h30

---

## 🔥 Cas d'Usage Critiques

### Cas 1: Daemon Crash Silencieux

**Scénario**: Daemon crash à 02:00 AM, personne ne remarque
**Sans monitoring**: Perte de TOUTES conversations jusqu'à détection manuelle
**Avec Phase 1**:
- Watchdog détecte en 60s
- Auto-restart daemon
- Alerte Discord → tu vois au réveil
- Perte: 0 conversations (reprise immédiate)

### Cas 2: API Down

**Scénario**: API crash, daemon continue mais fail à sauvegarder
**Sans monitoring**: Daemon log errors mais continue silencieusement
**Avec Phase 1**:
- Health check détecte "No recent imports"
- Alerte Discord "API unhealthy"
- Tu restart API manuellement
- Perte: 0 conversations (dedup évite doublons après restart)

### Cas 3: DB Connection Loss

**Scénario**: PostgreSQL restart, connection drops
**Sans monitoring**: Import fail, daemon continue
**Avec Phase 1**:
- Watchdog check DB connection
- Détecte loss + alerte
- Auto-restart daemon (reconnect)
- Perte: Conversations pendant downtime seulement

### Cas 4: Disk Full

**Scénario**: `/tmp/daemon.log` remplit le disque
**Sans monitoring**: Container crash, total outage
**Avec Phase 1**:
- Watchdog check disk usage
- Alerte si >90%
- Tu clean logs manuellement
- Prevention crash

---

## 🎓 Leçons des Systèmes Production

### Netflix Chaos Monkey Principle

**Citation**: "The best way to avoid failure is to fail constantly"

**Application MnemoLite**:
- Tester crash daemon régulièrement (1x/semaine)
- Vérifier auto-recovery fonctionne
- Mesurer MTTR (Mean Time To Recovery)

### Google SRE - Error Budget

**Citation**: "100% uptime is the wrong target"

**Application MnemoLite**:
- Acceptable: 1 restart/jour = 99.9% uptime
- Inacceptable: 10 restarts/jour = bug systémique

### AWS - Fail Fast, Recover Quickly

**Citation**: "It's not IF it fails, it's WHEN"

**Application MnemoLite**:
- Daemon doit fail fast (ne pas masquer erreurs)
- Watchdog doit recover quickly (60s detection)
- Alertes doivent être actionables (pas spam)

---

## 📊 Métriques de Succès

### KPIs Monitoring

```
┌─────────────────────────────────────────────────────┐
│ Métrique              │ Cible    │ Alerte          │
├───────────────────────┼──────────┼─────────────────┤
│ Daemon Uptime         │ >99%     │ <95%            │
│ Heartbeat Age         │ <60s     │ >120s           │
│ Import Success Rate   │ >95%     │ <80%            │
│ Time to Recovery      │ <120s    │ >300s           │
│ Alertes False Positives│ <5%     │ >20%            │
│ Conversations Lost    │ 0        │ >0              │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Prochaines Étapes (Si Tu Approuves Phase 1)

1. **Modifier daemon** (15min)
   - Ajouter heartbeat write
   - Ajouter metrics file
   - Improved error logging

2. **Créer watchdog** (30min)
   - Script shell externe
   - Auto-restart logic
   - Alert integration

3. **Health endpoint** (15min)
   - Nouveau route FastAPI
   - Check heartbeat age
   - Check recent imports

4. **Docker config** (10min)
   - Launch watchdog in background
   - Update healthcheck

5. **Testing** (20min)
   - Simuler crashes
   - Vérifier auto-restart
   - Tester alertes

**Total**: 1h30

---

**Attends validation avant de commencer l'implémentation.**

**Question Clé**: Phase 1 seule suffit? Ou tu veux aussi Phase 2 (dashboard)?

---

**Version**: 1.0.0
**Date**: 29 octobre 2025
**Auteur**: Claude Code Assistant
**Criticité**: MAXIMALE
**Status**: ⏳ PENDING USER APPROVAL
