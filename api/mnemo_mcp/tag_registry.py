"""
Registre central des conventions de tags (EPIC-60).

Unifie la casse et le vocabulaire des tags au write, sans jamais bloquer
l'écriture (validation DOUCE) : les écarts sont signalés dans `tag_warnings`
de la réponse de write_memory/update_memory.

Conventions (voir MCP_SETUP.md, section "Registre des conventions de tags") :
- Namespace `status:*` : casse canonique MAJUSCULE (status:CONFIRME), vocabulaire contraint.
- `fact:verifie` : obsolète, remplacé automatiquement par status:CONFIRME.
- `project:*`, `sys:*`, `session:*`, `date:*`, `source:*` : namespaces réservés, valeur libre.
- Les tags sans ':' sont des tags libres (aucun warning).
- Une mémoire taguée `kernel*` (pipeline KERNEL) sans tag `status:*` déclenche un warning.
"""

from typing import List, Optional, Tuple

# Namespaces documentés. None = valeur libre ; set = vocabulaire autorisé
# (casse canonique).
TAG_NAMESPACES = {
    "status": {"CONFIRME", "DOUTE", "REFUTE", "VERIFIE"},
    "fact": {"verifie"},  # obsolète : remplacé par status:CONFIRME
    "project": None,      # project:<nom> (ex: project:truth-engine)
    "sys": None,          # sys:<tag système> (ex: sys:history, sys:core)
    "session": None,      # session:<uuid> (auto-import)
    "date": None,         # date:<YYYYMMDD> (auto-import)
    "source": None,       # source:<name> (auto-import)
}

# Tags obsolètes : remplacés automatiquement au write (EPIC-60 T1.2).
OBSOLETE_TAGS = {
    "fact:verifie": "status:CONFIRME",
}


def process_tags(tags: Optional[List[str]]) -> Tuple[List[str], List[str]]:
    """Normalise les tags selon le registre EPIC-60.

    Args:
        tags: Tags bruts fournis au write (peut être None).

    Returns:
        (tags_normalises, warnings) : la normalisation est déterministe et
        non bloquante ; chaque écart produit un message de warning.
    """
    warnings: List[str] = []
    normalized: List[str] = []

    for raw in tags or []:
        tag = raw.strip()
        if not tag:
            continue
        lower = tag.lower()

        # 1. Tags obsolètes (fact:verifie -> status:CONFIRME)
        if lower in OBSOLETE_TAGS:
            replacement = OBSOLETE_TAGS[lower]
            warnings.append(f"tag obsolète '{tag}' remplacé par '{replacement}' (registre EPIC-60)")
            normalized.append(replacement)
            continue

        # 2. Namespace status : casse canonique MAJUSCULE + vocabulaire contraint
        if lower.startswith("status:"):
            value = tag.split(":", 1)[1] if ":" in tag else ""
            canonical = value.upper()
            if value != canonical:
                warnings.append(f"casse normalisée: '{tag}' -> 'status:{canonical}'")
            if canonical not in TAG_NAMESPACES["status"]:
                known = ", ".join(sorted(TAG_NAMESPACES["status"]))
                warnings.append(f"statut inconnu 'status:{canonical}' : valeurs connues {known}")
            normalized.append(f"status:{canonical}")
            continue

        # 3. Namespace réservé connu : inchangé
        ns = tag.split(":", 1)[0]
        if ns in TAG_NAMESPACES:
            normalized.append(tag)
            continue

        # 4. Namespace inconnu (tag avec ':') : warning, tag conservé tel quel
        if ":" in tag:
            warnings.append(f"namespace de tag inconnu '{ns}:' (voir registre EPIC-60 dans MCP_SETUP.md)")
        normalized.append(tag)

    # 5. Mémoire issue du pipeline KERNEL sans statut forensique
    has_status = any(t.lower().startswith("status:") for t in normalized)
    has_kernel = any(t.lower().startswith("kernel") for t in normalized)
    if has_kernel and not has_status:
        warnings.append(
            "mémoire taguée 'kernel*' (pipeline KERNEL) sans tag status:* : "
            "ajouter status:CONFIRME/DOUTE/REFUTE si fait vérifié"
        )

    return normalized, warnings
