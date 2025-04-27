Voici un **mémo d’implémentation PDM** destiné à un LLM-développeur chargé d’intégrer la solution dans MnemoLite.  
Il suit la structure Expanse (Ω-Φ-Ξ-Λ-M-Ψ) ; chaque section décrit **pourquoi**, **comment** et **avec quels outils** installer PDM, ses plugins clés, ainsi que la chaîne CI/CD GitHub Actions.

---

## Ω · Contexte & Objectifs

MnemoLite vise une stack allégée : 3 conteneurs Docker (`db`, `api`, `worker`) et du **Python 3.12-slim**.  
Adopter **PDM** (PEP 621/517/582) garantit un lockfile déterministe, un résolveur rapide et la possibilité de gérer scripts & plugins sans alourdir le Dockerfile  ([PDM: Introduction](https://pdm-project.org/?utm_source=chatgpt.com)).  
Le but est d’obtenir :

* **Images finales ≤ 430 MB** et un **build < 90 s** en cache chaud.  
* Un **pipeline « security-first »** : audit CVE + génération d’un SBOM SPDX/CycloneDX.  
* Des **mises à jour dépendances automatisées** (PR hebdo).

---

## Φ · Alternatives & Choix

| Option | Verdict | Raison |
|--------|---------|--------|
| pip + req.txt | **Rejeté** | Résolution lente, dérive versions. |
| Poetry | **Rejeté** | Images +130 MB, build plus lent ; pas de PEP 582. |
| **PDM** | **Adopté** | Lockfile cross-platform, plugins Docker/SBOM, support PEP 582  ([Awesome PDM | awesome-pdm](https://awesome.pdm-project.org/?utm_source=chatgpt.com)) |

---

## Ξ · Implémentation locale & Docker

### 1. Installation locale (dev)

```bash
brew install pdm           # macOS
pipx install pdm           # Linux/WSL
pdm plugin add pdm-autoexport pdm-audit pdm-sbom pdm-readiness
```

* **pdm-autoexport** maintient `requirements.txt` à jour après chaque `pdm lock`  ([pdm-project/pdm-autoexport: A PDM plugin to sync the ... - GitHub](https://github.com/pdm-project/pdm-autoexport?utm_source=chatgpt.com)).  
* **pdm-audit** lance `pip-audit` automatiquement  ([Awesome PDM | awesome-pdm](https://awesome.pdm-project.org/?utm_source=chatgpt.com)).  
* **pdm-sbom** génère le SBOM (`pdm sbom --format spdx`)  ([carstencodes/pdm-sbom: Generate Software Bill of ... - GitHub](https://github.com/carstencodes/pdm-sbom?utm_source=chatgpt.com)).  
* **pdm-readiness** vérifie la compatibilité Python 3.12  ([A curated list of awesome PDM plugins and resources - GitHub](https://github.com/pdm-project/awesome-pdm?utm_source=chatgpt.com)).

### 2. Docker multi-stage (*pdm-dockerize*)

```dockerfile
# ---- builder ----
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir pdm pdm-dockerize
COPY pyproject.toml pdm.lock ./
RUN pdm dockerize --prod -t mnemo-api:latest .

# ---- final ----
FROM scratch AS final
COPY --from=builder /opt/app /opt/app
CMD ["python", "-m", "mnemo.api"]
```

Le plugin **pdm-dockerize** filtre les binaires inutiles et copie `__pypackages__` compressé  ([Help generating docker images from PDM projects - GitHub](https://github.com/noirbizarre/pdm-dockerize?utm_source=chatgpt.com)), réduisant l’image de ~40 MB par rapport à Poetry.

### 3. Alternative : export offline

Si le workflow CI impose `pip install` :

```bash
pdm export -o requirements.txt --prod --without-hashes
```

Puis Dockerfile classique.  
Ajoutez **pdm-download** pour pré-télécharger wheels en environnement air-gap  ([Awesome PDM | awesome-pdm](https://awesome.pdm-project.org/?utm_source=chatgpt.com)).

---

## Λ · Chaîne CI/CD GitHub Actions

```yaml
name: build-test
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - uses: pdm-project/setup-pdm@v4      # installe & met en cache PDM  ([A GitHub Action that installs pdm properly for all Python versions](https://github.com/pdm-project/setup-pdm?utm_source=chatgpt.com))
        with:
          python-version: "3.12"
      - run: pdm install -G :all
      - run: pdm audit                      # bloque sur CVE  ([Awesome PDM | awesome-pdm](https://awesome.pdm-project.org/?utm_source=chatgpt.com))
      - run: pdm sbom --format spdx         # conformité SPDX  ([SPDX Tools](https://spdx.dev/use/spdx-tools/?utm_source=chatgpt.com))
      - run: pdm run pytest
      - run: pdm dockerize --prod -t mnemo-api:${{ github.sha }} .
      - uses: docker/metadata-action@v5
```

### Actions complémentaires

| Action | Fonction | Source |
|--------|----------|--------|
| **setup-pdm** | Installe & met en cache PDM |  ([Actions · GitHub Marketplace - Setup PDM](https://github.com/marketplace/actions/setup-pdm?utm_source=chatgpt.com)) |
| **update-deps-action** | PR hebdo `pdm update --update-all` |  ([Activity · pdm-project/awesome-pdm - GitHub](https://github.com/pdm-project/awesome-pdm/activity?utm_source=chatgpt.com)) |
| **SBOM upload** | Publier le fichier SPDX dans les artefacts | (native `actions/upload-artifact`) |

---

## M · KPI à surveiller (CI « health »)

| KPI | Seuil | Script |
|-----|-------|--------|
| Build Docker | ≤ 90 s | `time docker build .` |
| Image finale | ≤ 430 MB | `docker images mnemo-api` |
| Vulnérabilités | 0 CVE “High” | `pdm audit --output-json` |
| SBOM généré | oui | présence `mnemo-api.spdx.json` |
| Lock drift | 0 | `pdm lock --check` |

Intégrez ces vérifications dans la cible `make health`.

---

## Ψ · Feuille de route & commandes Expanse

1. **Créer la règle CI sécurité** :

```text
@Expanse create_rule("rule_pdm_security", desc="CI job pdm audit + sbom + image size")
```

2. **Automatiser l’export** (si option export retenue) :

```text
@Expanse create_rule("rule_pdm_autoexport", desc="post-commit pdm autoexport")
```

3. **Gouvernance dépendances** : planifier `update-deps-action` chaque lundi à 06:00 UTC.  

4. **Surveillance IDE** : recommander le plugin **pdm-vscode** pour générer `settings.json` et pointer `__pypackages__`  ([A curated list of awesome PDM plugins and resources - GitHub](https://github.com/pdm-project/awesome-pdm?utm_source=chatgpt.com)).

---

### Résumé exécutif

* **Installez PDM + plugins essentiels** (`audit`, `sbom`, `autoexport`, `dockerize`, `readiness`).  
* **Utilisez `pdm-dockerize`** pour générer des images minces et reproductibles ; sinon, **export requirements** et cachez les wheels.  
* **Équipez la CI** avec `setup-pdm`, un job d’audit CVE, la génération SBOM, et `update-deps-action`.  
* **Surveillez quatre KPI** (image, build, vulnérabilités, drift).  
* **Documentez** toutes les commandes dans `DEV.md` et les règles Expanse correspondantes.

Avec ces éléments, le LLM-développeur dispose d’un **guide complet** pour intégrer PDM de façon sécurisée, performante et entièrement automatisée dans MnemoLite.