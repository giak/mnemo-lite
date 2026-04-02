# EPIC-30: Complete Observability — Alerting UI

**Status**: ✅ COMPLETE | **Created**: 2026-04-02 | **Completed**: 2026-04-02

---

## Context

EPIC-22 (Observability) est à 53% — le backend est complet mais l'UI d'alerting manque.
L'objectif est de pouvoir **diagnostiquer tout problème de production en 30 secondes** depuis l'interface.

### Ce qui existe déjà (EPIC-22 Phase 1-2)
- ✅ Monitoring routes (status, events, metrics)
- ✅ Advanced monitoring (summary, logs stream, performance, alerts, ACK)
- ✅ Performance routes (metrics, cache, system, DB pool, slow queries, indexes)
- ✅ Frontend Monitoring.vue (latency chart, alert summary, recent alerts)
- ✅ LatencyChart.vue component
- ✅ Alert ACK functionality (backend)

### Ce qui manque
- ❌ Gestion des règles d'alerte (créer/modifier/supprimer)
- ❌ Dashboard d'alertes en temps réel
- ❌ Configuration des seuils d'alerte
- ❌ Historique des alertes avec filtrage

---

## Stories

### Story 30.1: Alert Rule Management UI
**Priority**: P0 | **Effort**: 2 pts | **Value**: High

Interface CRUD pour gérer les règles d'alerte depuis le front.

**Fonctionnalités** :
- Liste des règles actives avec statut (enabled/disabled)
- Formulaire de création : nom, métrique, seuil, sévérité, cooldown
- Édition inline des règles existantes
- Suppression avec confirmation
- Toggle enable/disable rapide

**Fichiers à créer** :
- `frontend/src/components/AlertRuleEditor.vue`
- `frontend/src/composables/useAlertRules.ts`

**Fichiers à modifier** :
- `frontend/src/pages/Monitoring.vue` — ajouter onglet "Alert Rules"
- `api/routes/monitoring_routes_advanced.py` — endpoints CRUD si manquants

---

### Story 30.2: Real-time Alert Dashboard
**Priority**: P0 | **Effort**: 2 pts | **Value**: High

Dashboard dédié aux alertes avec vue temps réel et historique.

**Fonctionnalités** :
- Timeline des alertes récentes (dernières 24h)
- Filtrage par : sévérité, source, statut (active/acknowledged/resolved)
- Compteur d'alertes actives dans la navbar (badge)
- Auto-refresh 15s
- Export CSV des alertes

**Fichiers à créer** :
- `frontend/src/pages/Alerts.vue`
- `frontend/src/components/AlertTimeline.vue`
- `frontend/src/composables/useAlerts.ts`

**Fichiers à modifier** :
- `frontend/src/router.ts` — ajouter route `/alerts`
- `frontend/src/components/Navbar.vue` — badge compteur d'alertes actives

---

### Story 30.3: Alert Threshold Configuration
**Priority**: P1 | **Effort**: 2 pts | **Value**: Medium

Configuration avancée des seuils d'alerte avec presets.

**Fonctionnalités** :
- Presets de seuils par environnement (dev, staging, prod)
- Configuration du cooldown entre alertes (éviter le spam)
- Notification channels (email, webhook, Slack — stub pour l'instant)
- Test d'alerte (envoyer une alerte de test pour valider la config)

**Fichiers à créer** :
- `frontend/src/components/AlertThresholdConfig.vue`
- `frontend/src/components/AlertTestButton.vue`

**Fichiers à modifier** :
- `frontend/src/components/AlertRuleEditor.vue` — intégrer la config de seuils

---

## Critères de complétion

- [ ] CRUD des règles d'alerte fonctionnel depuis l'UI
- [ ] Dashboard d'alertes avec timeline et filtres
- [ ] Badge compteur d'alertes actives dans la navbar
- [ ] Configuration des seuils avec presets
- [ ] Auto-refresh 15s sur le dashboard d'alertes
- [ ] EPIC-22 à 100% complet

---

## Ordre d'exécution

```
30.1 (Alert Rules CRUD) → 30.2 (Alert Dashboard) → 30.3 (Threshold Config)
```
