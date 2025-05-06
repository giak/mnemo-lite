#!/bin/bash

# Couleurs pour la sortie
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Updated API URLs
API_URL_EVENTS="http://localhost:8001/v1/_test_only/events" # Use test endpoint for setup/teardown
API_URL_SEARCH="http://localhost:8001/v1/search" # Use search endpoint for testing queries

# Fonction pour afficher les messages d'en-tête
print_header() {
    echo -e "\n${BLUE}==== $1 ====${NC}"
}

# Fonction pour vérifier si une commande a réussi (basé sur code de sortie)
check_success() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Succès: $1${NC}"
    else
        echo -e "${RED}✗ Échec: $1 - Vérifiez la sortie ci-dessus.${NC}"
        # Ne pas sortir immédiatement pour permettre l'exécution de tous les tests
        # exit 1 
    fi
}

# Fonction pour vérifier un code HTTP spécifique
check_http_code() {
    RESPONSE_CODE=$1
    EXPECTED_CODE=$2
    TEST_NAME=$3
    
    if [ "$RESPONSE_CODE" -eq "$EXPECTED_CODE" ]; then
        echo -e "${GREEN}✓ Succès: $TEST_NAME (Code HTTP: $RESPONSE_CODE)${NC}"
        return 0
    else
        echo -e "${RED}✗ Échec: $TEST_NAME (Code HTTP: $RESPONSE_CODE, attendu: $EXPECTED_CODE)${NC}"
        # exit 1 # Ne pas sortir pour voir toutes les erreurs
        return 1
    fi
}

# Fonction pour vérifier si un JSON contient un certain nombre d'éléments dans 'data'
check_data_count() {
    JSON_RESPONSE="$1"
    EXPECTED_COUNT=$2
    TEST_NAME="$3"
    
    ACTUAL_COUNT=$(echo "$JSON_RESPONSE" | jq '.data | length')
    
    if [[ "$ACTUAL_COUNT" == "$EXPECTED_COUNT" ]]; then
         echo -e "${GREEN}✓ Succès: $TEST_NAME (Trouvé $ACTUAL_COUNT éléments)${NC}"
         return 0
    else
         echo -e "${RED}✗ Échec: $TEST_NAME (Trouvé $ACTUAL_COUNT éléments, attendu $EXPECTED_COUNT)${NC}"
         echo "Réponse JSON:"
         echo "$JSON_RESPONSE" | jq
         return 1
    fi
}

# Fonction pour vérifier le total_hits dans meta
check_total_hits() {
    JSON_RESPONSE="$1"
    EXPECTED_COUNT=$2
    TEST_NAME="$3"
    
    ACTUAL_COUNT=$(echo "$JSON_RESPONSE" | jq '.meta.total_hits')
    
    if [[ "$ACTUAL_COUNT" == "$EXPECTED_COUNT" ]]; then
         echo -e "${GREEN}✓ Succès: $TEST_NAME (total_hits = $ACTUAL_COUNT)${NC}"
         return 0
    else
         echo -e "${RED}✗ Échec: $TEST_NAME (total_hits = $ACTUAL_COUNT, attendu $EXPECTED_COUNT)${NC}"
         echo "Réponse JSON:"
         echo "$JSON_RESPONSE" | jq
        return 1
    fi
}

# Fonction pour imprimer une section
print_section() {
    echo -e "\n${YELLOW}--- $1 ---${NC}"
}

echo -e "${BLUE}==================================================================${NC}"
echo -e "${BLUE}      TEST COMPLET DE L'API EVENTS & SEARCH (v1)                ${NC}"
echo -e "${BLUE}==================================================================${NC}"

# Nettoyage initial (Optionnel, dépend si on veut repartir de zéro)
# echo "Nettoyage initial des événements de test..."
# curl -s -X DELETE "${API_URL_EVENTS}/by_tag/test_script" > /dev/null
# curl -s -X DELETE "${API_URL_EVENTS}/by_tag/filter-test" > /dev/null
# curl -s -X DELETE "${API_URL_EVENTS}/by_tag/search-test" > /dev/null


###############################################
print_header "1. TESTS DE BASE SUR EVENTS (/v1/_test_only/events)"
###############################################

# Générer un ID aléatoire pour les tests (utile pour certains contenus/métadonnées)
TEST_RUN_UUID=$(cat /proc/sys/kernel/random/uuid)
echo -e "${BLUE}UUID de cette exécution de test: ${TEST_RUN_UUID}${NC}"

print_section "1.1 CREATE - Créer un nouvel événement"
# Utilisation de _test_only endpoint
# Generate a full 1536-dim embedding
EMBEDDING_CRUD=$(python3 -c "import json; print(json.dumps([0.1]*1536))") 
CREATE_RESPONSE=$(curl -s -X POST "${API_URL_EVENTS}/" \
    -H "Content-Type: application/json" \
    -d '{
        "content": {
            "message": "Ceci est un test de création d_événement via endpoint test",
            "source": "test_script",
            "run_id": "'"$TEST_RUN_UUID"'"
        },
        "metadata": {
            "test": true,
            "created_by": "test_script",
            "tag": "crud_test_'"$TEST_RUN_UUID"'"
        },
        "embedding": '"$EMBEDDING_CRUD"'
    }')

# Vérifier la réponse (doit retourner l'événement créé)
echo "$CREATE_RESPONSE" | jq
check_success "Création d'événement (via endpoint test)"

# Extraire l'ID de la réponse
EVENT_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')
if [ -z "$EVENT_ID" ] || [ "$EVENT_ID" == "null" ]; then
    echo -e "${RED}✗ Échec: Impossible d'extraire l'ID de l'événement créé.${NC}"
    exit 1
fi
echo -e "${BLUE}ID événement créé: ${EVENT_ID}${NC}"

print_section "1.2 READ - Récupérer un événement par son ID (via endpoint test)"
# Utilisation de _test_only endpoint GET /{id}
READ_RESPONSE=$(curl -s -X GET "${API_URL_EVENTS}/${EVENT_ID}")
echo "$READ_RESPONSE" | jq
check_success "Lecture d'événement (via endpoint test)"

# Vérifier que l'ID correspond
READ_ID=$(echo "$READ_RESPONSE" | jq -r '.id')
if [ "$READ_ID" != "$EVENT_ID" ]; then
    echo -e "${RED}✗ Échec: L'ID lu ne correspond pas à l'ID créé ($READ_ID != $EVENT_ID).${NC}"
fi


# NOTE: Les endpoints UPDATE et DELETE standard (/v1/events/{id}) ne sont pas testés ici.
# On utilise le endpoint de test pour la suppression à la fin.

###############################################
print_header "2. TESTS DES CAS D'ERREUR (Search & Events)"
###############################################

print_section "2.1 SEARCH avec filtre JSON invalide"
INVALID_FILTER_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL_SEARCH}/?filter_metadata=\{invalid")
check_http_code "$INVALID_FILTER_RESPONSE" 400 "Recherche avec filtre JSON invalide" || echo "Ce test a échoué mais nous continuons"

print_section "2.2 SEARCH avec timestamp invalide (ts_start)"
INVALID_TS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL_SEARCH}/?ts_start=not-a-date")
check_http_code "$INVALID_TS_RESPONSE" 400 "Recherche avec ts_start invalide" || echo "Ce test a échoué mais nous continuons"

print_section "2.3 SEARCH avec vecteur JSON invalide (vector_query)"
INVALID_VEC_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL_SEARCH}/?vector_query=\\[1,2,")
check_http_code "$INVALID_VEC_RESPONSE" 422 "Recherche avec vector_query JSON invalide" || echo "Ce test a échoué mais nous continuons"

print_section "2.4 SEARCH avec vecteur non-liste (vector_query)"
INVALID_VEC_TYPE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL_SEARCH}/?vector_query=\\{\\\"vec\\\":true\\}")
check_http_code "$INVALID_VEC_TYPE_RESPONSE" 422 "Recherche avec vector_query non-liste" || echo "Ce test a échoué mais nous continuons"

print_section "2.5 GET Event avec ID au format invalide"
INVALID_ID="not-a-valid-uuid"
INVALID_ID_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL_EVENTS}/${INVALID_ID}")
check_http_code "$INVALID_ID_RESPONSE" 422 "GET Event avec ID invalide" || echo "Ce test a échoué mais nous continuons"

print_section "2.6 GET Event avec un ID UUID valide mais inexistant"
NONEXISTENT_ID="11111111-1111-1111-1111-111111111111"
NONEXISTENT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL_EVENTS}/${NONEXISTENT_ID}")
check_http_code "$NONEXISTENT_RESPONSE" 404 "GET Event avec ID inexistant" || echo "Ce test a échoué mais nous continuons"

print_section "2.7 POST Event avec données incomplètes (content manquant)"
INVALID_CREATE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL_EVENTS}/" \
    -H "Content-Type: application/json" \
    -d '{
        "metadata": {"test": true},
        "embedding": [0.1] 
    }')
check_http_code "$INVALID_CREATE_RESPONSE" 422 "POST Event avec content manquant" || echo "Ce test a échoué mais nous continuons"

###############################################
print_header "3. TESTS AVEC DONNÉES COMPLEXES (via /v1/_test_only/events)"
###############################################

print_section "3.1 CREATE avec contenu complexe et multilingue"
# Generate a full 1536-dim embedding
EMBEDDING_COMPLEX=$(python3 -c "import json; print(json.dumps([0.5]*1536))") 
COMPLEX_CONTENT_RESPONSE=$(curl -s -X POST "${API_URL_EVENTS}/" \
    -H "Content-Type: application/json" \
    -d '{
        "content": {
            "title": "Test complexe",
            "description": "Description avec caractères spéciaux: éèêëàâäôöùûüÿç",
            "items": [
                {"id": 1, "value": "Premier élément"},
                {"id": 2, "value": "Deuxième élément"}
            ],
            "nested": { "level1": { "level2": "Données profondément imbriquées" } }
        },
        "metadata": {
            "tags": ["test", "complex", "multilingual", "created_by_script_'"$TEST_RUN_UUID"'"],
            "priority": 10,
            "active": true,
            "dimensions": { "width": 100, "height": 200 }
        },
        "embedding": '"$EMBEDDING_COMPLEX"' 
    }')

echo "$COMPLEX_CONTENT_RESPONSE" | jq
check_success "Création événement avec contenu complexe"

COMPLEX_ID=$(echo "$COMPLEX_CONTENT_RESPONSE" | jq -r '.id')
if [ -z "$COMPLEX_ID" ] || [ "$COMPLEX_ID" == "null" ]; then
    echo -e "${RED}✗ Échec: Impossible d'extraire l'ID de l'événement complexe.${NC}"
else
    echo -e "${BLUE}ID événement complexe: ${COMPLEX_ID}${NC}"

# Vérifier que toutes les données sont bien sauvegardées
    print_section "3.2 READ de l'événement avec contenu complexe"
    COMPLEX_READ=$(curl -s -X GET "${API_URL_EVENTS}/${COMPLEX_ID}")
echo "$COMPLEX_READ" | jq
    check_success "Lecture événement avec contenu complexe"
fi

# Nettoyage à la fin du script

###############################################
print_header "4. TESTS DE FILTRAGE ET PAGINATION (/v1/search/)"
###############################################

# Créer quelques événements pour les tests de filtrage/pagination
print_section "4.1 Création d'événements pour le test de filtrage/pagination"
FILTER_TAG="filter_test_${TEST_RUN_UUID}"
EVENT_IDS_FILTER=()

for i in {0..6}; do
    CAT=$(( ( RANDOM % 2 ) + 1 )) # Catégorie 1 ou 2
    TS=$(date -u -d "-${i} hour" '+%Y-%m-%dT%H:%M:%SZ') # Timestamps distincts UTC
    # Generate embedding for filter tests
    FILTER_EMBEDDING=$(python3 -c "import json; print(json.dumps([0.3 + $i * 0.01]*1536))")
    EV_RESPONSE=$(curl -s -X POST "${API_URL_EVENTS}/" \
    -H "Content-Type: application/json" \
    -d '{
            "content": {"message": "Event for filtering P'",$i,"'"},
            "metadata": {"category": "CAT'$CAT'", "tag": "'"$FILTER_TAG"'", "index": '$i'},
            "timestamp": "'"$TS"'",
            "embedding": '"$FILTER_EMBEDDING"' 
        }')
    EV_ID=$(echo "$EV_RESPONSE" | jq -r '.id')
    EVENT_IDS_FILTER+=("$EV_ID")
    echo "Événement '$FILTER_TAG' $i créé (Cat $CAT, TS $TS): ${EV_ID}"
done
sleep 1 # Attendre potentielle indexation


print_section "4.2 Recherche avec filtre metadata simple (tag)"
FILTER_RESPONSE=$(curl -s -G "${API_URL_SEARCH}/" --data-urlencode "filter_metadata={\"tag\":\"$FILTER_TAG\"}" --data-urlencode "limit=10")
echo "$FILTER_RESPONSE" | jq
check_success "Filtrage metadata simple (tag)"
check_data_count "$FILTER_RESPONSE" 7 "Filtrage metadata simple (tag) - Nombre d'éléments"
check_total_hits "$FILTER_RESPONSE" 7 "Filtrage metadata simple (tag) - Total hits"

print_section "4.3 Recherche avec filtre metadata combiné (tag et category)"
FILTER_RESPONSE_COMB=$(curl -s -G "${API_URL_SEARCH}/" --data-urlencode "filter_metadata={\"tag\":\"$FILTER_TAG\", \"category\":\"CAT1\"}" --data-urlencode "limit=10")
echo "$FILTER_RESPONSE_COMB" | jq
COUNT_CAT1=$(echo "$FILTER_RESPONSE_COMB" | jq '.data | length')
echo "Nombre d'éléments trouvés pour CAT1: $COUNT_CAT1"
check_success "Filtrage metadata combiné (tag+cat)"
# Le nombre total de hits devrait correspondre au nombre réel de CAT1
TOTAL_HITS_CAT1=$(echo "$FILTER_RESPONSE_COMB" | jq '.meta.total_hits')
if [[ "$COUNT_CAT1" == "$TOTAL_HITS_CAT1" ]]; then
    echo -e "${GREEN}✓ Succès: total_hits correspond au nombre trouvé pour CAT1 ($TOTAL_HITS_CAT1)${NC}"
else
     echo -e "${RED}✗ Échec: total_hits ($TOTAL_HITS_CAT1) != nombre trouvé ($COUNT_CAT1) pour CAT1 ${NC}"
fi

print_section "4.4 Recherche avec filtre temporel (ts_start / ts_end)"
# Chercher les événements des 3 dernières heures
TS_END=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
TS_START=$(date -u -d "-3 hour" '+%Y-%m-%dT%H:%M:%SZ')
TIME_FILTER_RESPONSE=$(curl -s -G "${API_URL_SEARCH}/" \
    --data-urlencode "filter_metadata={\"tag\":\"$FILTER_TAG\"}" \
    --data-urlencode "ts_start=$TS_START" \
    --data-urlencode "ts_end=$TS_END" \
    --data-urlencode "limit=10")
echo "$TIME_FILTER_RESPONSE" | jq
check_success "Filtrage temporel"
check_data_count "$TIME_FILTER_RESPONSE" 4 "Filtrage temporel (3h) - Nombre d'éléments" # 0, 1, 2, 3 heures passées
check_total_hits "$TIME_FILTER_RESPONSE" 4 "Filtrage temporel (3h) - Total hits"

print_section "4.5 Test de pagination (limit et offset)"
# Récupérer les 3 premiers résultats (les plus récents par défaut)
PAGE1=$(curl -s -G "${API_URL_SEARCH}/" --data-urlencode "filter_metadata={\"tag\":\"$FILTER_TAG\"}" --data-urlencode "limit=3" --data-urlencode "offset=0")
check_success "Pagination - Page 1 GET"
check_data_count "$PAGE1" 3 "Pagination - Page 1 Count"
check_total_hits "$PAGE1" 7 "Pagination - Page 1 Total Hits"
echo "Contenu Page 1:"
echo "$PAGE1" | jq '.data[] | .content.message'

# Récupérer les 3 résultats suivants
PAGE2=$(curl -s -G "${API_URL_SEARCH}/" --data-urlencode "filter_metadata={\"tag\":\"$FILTER_TAG\"}" --data-urlencode "limit=3" --data-urlencode "offset=3")
check_success "Pagination - Page 2 GET"
check_data_count "$PAGE2" 3 "Pagination - Page 2 Count"
check_total_hits "$PAGE2" 7 "Pagination - Page 2 Total Hits"
echo "Contenu Page 2:"
echo "$PAGE2" | jq '.data[] | .content.message'

# Récupérer la dernière page (1 résultat)
PAGE3=$(curl -s -G "${API_URL_SEARCH}/" --data-urlencode "filter_metadata={\"tag\":\"$FILTER_TAG\"}" --data-urlencode "limit=3" --data-urlencode "offset=6")
check_success "Pagination - Page 3 GET"
check_data_count "$PAGE3" 1 "Pagination - Page 3 Count"
check_total_hits "$PAGE3" 7 "Pagination - Page 3 Total Hits"
echo "Contenu Page 3:"
echo "$PAGE3" | jq '.data[] | .content.message'


###############################################
print_header "5. TESTS DE RECHERCHE VECTORIELLE & HYBRIDE (/v1/search/)"
###############################################

print_section "5.1 Création d'événements pour le test de recherche"
SEARCH_TAG="search_test_${TEST_RUN_UUID}"
EVENT_IDS_SEARCH=()
NOW=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

# Événement 1 (Log, 2h ago)
TS1=$(date -u -d "-2 hour" '+%Y-%m-%dT%H:%M:%SZ')
EV1_CONTENT='{"text": "Ceci est le premier log pour la recherche vectorielle.", "lang": "fr"}'
EV1_META='{"source": "search_test", "type": "log", "tag": "'"$SEARCH_TAG"'", "nested": {"val": 1}}'
# Générer un embedding spécifique (exemple simple, devrait être plus réaliste)
EV1_EMBEDDING=$(python3 -c "import json; print(json.dumps([0.1]*1536))") 
EV1_RESPONSE=$(curl -s -X POST "${API_URL_EVENTS}/" -H "Content-Type: application/json" -d '{ "content": '"$EV1_CONTENT"', "metadata": '"$EV1_META"', "timestamp": "'"$TS1"'", "embedding": '"$EV1_EMBEDDING"' }')
EV1_ID=$(echo "$EV1_RESPONSE" | jq -r '.id')
EVENT_IDS_SEARCH+=("$EV1_ID")
echo "Event 1 (Log, Vec 0.1) créé: ${EV1_ID}"

# Événement 2 (Metric, 1h ago)
TS2=$(date -u -d "-1 hour" '+%Y-%m-%dT%H:%M:%SZ')
EV2_CONTENT='{"value": 42, "unit": "test/sec"}'
EV2_META='{"source": "search_test", "type": "metric", "tag": "'"$SEARCH_TAG"'", "nested": {"val": 2}}'
EV2_EMBEDDING=$(python3 -c "import json; print(json.dumps([0.9]*1536))") 
EV2_RESPONSE=$(curl -s -X POST "${API_URL_EVENTS}/" -H "Content-Type: application/json" -d '{ "content": '"$EV2_CONTENT"', "metadata": '"$EV2_META"', "timestamp": "'"$TS2"'", "embedding": '"$EV2_EMBEDDING"' }')
EV2_ID=$(echo "$EV2_RESPONSE" | jq -r '.id')
EVENT_IDS_SEARCH+=("$EV2_ID")
echo "Event 2 (Metric, Vec 0.9) créé: ${EV2_ID}"

# Événement 3 (Log, 30m ago)
TS3=$(date -u -d "-30 minute" '+%Y-%m-%dT%H:%M:%SZ')
EV3_CONTENT='{"text": "Un autre log, différent du premier.", "lang": "fr"}'
EV3_META='{"source": "search_test", "type": "log", "tag": "'"$SEARCH_TAG"'", "nested": {"val": 3}}'
EV3_EMBEDDING=$(python3 -c "import json; print(json.dumps([0.2]*1536))") 
EV3_RESPONSE=$(curl -s -X POST "${API_URL_EVENTS}/" -H "Content-Type: application/json" -d '{ "content": '"$EV3_CONTENT"', "metadata": '"$EV3_META"', "timestamp": "'"$TS3"'", "embedding": '"$EV3_EMBEDDING"' }')
EV3_ID=$(echo "$EV3_RESPONSE" | jq -r '.id')
EVENT_IDS_SEARCH+=("$EV3_ID")
echo "Event 3 (Log, Vec 0.2) créé: ${EV3_ID}"
sleep 1


print_section "5.2 Recherche vectorielle seule (avec texte -> embedding)"
# Devrait trouver l'événement 1 comme le plus proche (si le service d'embedding simple est déterministe)
VEC_TEXT_QUERY="premier log recherche"
VEC_TEXT_RESPONSE=$(curl -s -G "${API_URL_SEARCH}/" \
    --data-urlencode "vector_query=$VEC_TEXT_QUERY" \
    --data-urlencode "limit=5")
echo "$VEC_TEXT_RESPONSE" | jq
check_success "Recherche vectorielle (texte)"
# Difficile de prédire le nombre exact ou l'ordre sans connaître le modèle d'embedding exact
# On vérifie juste qu'on a des résultats et un total_hits > 0
VEC_TEXT_COUNT=$(echo "$VEC_TEXT_RESPONSE" | jq '.data | length')
VEC_TEXT_TOTAL=$(echo "$VEC_TEXT_RESPONSE" | jq '.meta.total_hits')
if [[ $VEC_TEXT_COUNT -gt 0 ]] && [[ $VEC_TEXT_TOTAL -gt 0 ]]; then
     echo -e "${GREEN}✓ Succès: Recherche vectorielle (texte) a retourné des résultats ($VEC_TEXT_COUNT / $VEC_TEXT_TOTAL)${NC}"
else
     echo -e "${RED}✗ Échec: Recherche vectorielle (texte) n'a retourné aucun résultat.${NC}"
fi

print_section "5.3 Recherche vectorielle seule (avec vecteur JSON)"
# Utiliser l'embedding de l'événement 1 pour le chercher
VEC_JSON_RESPONSE=$(curl -s -G "${API_URL_SEARCH}/" \
    --data-urlencode "vector_query=$EV1_EMBEDDING" \
    --data-urlencode "limit=5")
echo "$VEC_JSON_RESPONSE" | jq
check_success "Recherche vectorielle (JSON)"
check_data_count "$VEC_JSON_RESPONSE" 1 "Recherche vectorielle (JSON) - Nombre attendu (1)" # Devrait trouver EV1
check_total_hits "$VEC_JSON_RESPONSE" 1 "Recherche vectorielle (JSON) - Total hits (1)"
FIRST_RESULT_ID=$(echo "$VEC_JSON_RESPONSE" | jq -r '.data[0].id')
if [[ "$FIRST_RESULT_ID" == "$EV1_ID" ]]; then
     echo -e "${GREEN}✓ Succès: Recherche vectorielle (JSON) a trouvé le bon ID ($EV1_ID)${NC}"
else
     echo -e "${RED}✗ Échec: Recherche vectorielle (JSON) n'a pas trouvé le bon ID ($FIRST_RESULT_ID != $EV1_ID).${NC}"
fi


print_section "5.4 Recherche hybride (Vecteur JSON + Metadata + Temps)"
# Chercher les "logs" (type:log) similaires à l'événement 3 ([0.2,..]) créés dans les 90 dernières minutes
TS_HYBRID_START=$(date -u -d "-90 minute" '+%Y-%m-%dT%H:%M:%SZ')
TS_HYBRID_END=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
HYBRID_META='{"type": "log", "source": "search_test"}'
HYBRID_VEC=$(python3 -c "import json; print(json.dumps([0.21]*1536))") # Vecteur proche de EV3

HYBRID_RESPONSE=$(curl -s -G "${API_URL_SEARCH}/" \
    --data-urlencode "vector_query=$HYBRID_VEC" \
    --data-urlencode "filter_metadata=$HYBRID_META" \
    --data-urlencode "ts_start=$TS_HYBRID_START" \
    --data-urlencode "ts_end=$TS_HYBRID_END" \
    --data-urlencode "limit=5")
echo "$HYBRID_RESPONSE" | jq
check_success "Recherche hybride"
check_data_count "$HYBRID_RESPONSE" 1 "Recherche hybride - Nombre attendu (1)" # Devrait trouver seulement EV3
check_total_hits "$HYBRID_RESPONSE" 1 "Recherche hybride - Total hits (1)"
FIRST_HYBRID_ID=$(echo "$HYBRID_RESPONSE" | jq -r '.data[0].id')
if [[ "$FIRST_HYBRID_ID" == "$EV3_ID" ]]; then
     echo -e "${GREEN}✓ Succès: Recherche hybride a trouvé le bon ID ($EV3_ID)${NC}"
else
     echo -e "${RED}✗ Échec: Recherche hybride n'a pas trouvé le bon ID ($FIRST_HYBRID_ID != $EV3_ID).${NC}"
fi


###############################################
print_header "6. NETTOYAGE FINAL"
###############################################
print_section "Suppression des événements de test créés"

# Supprimer l'événement du test CRUD initial (s'il existe encore)
if [ -n "$EVENT_ID" ]; then
    curl -s -X DELETE "${API_URL_EVENTS}/${EVENT_ID}" > /dev/null
    echo "Tentative de suppression de l'événement CRUD: ${EVENT_ID}"
fi

# Supprimer l'événement complexe (s'il existe encore)
if [ -n "$COMPLEX_ID" ]; then
    curl -s -X DELETE "${API_URL_EVENTS}/${COMPLEX_ID}" > /dev/null
    echo "Tentative de suppression de l'événement complexe: ${COMPLEX_ID}"
fi

# Supprimer les événements de filtrage
for id in "${EVENT_IDS_FILTER[@]}"; do
    curl -s -X DELETE "${API_URL_EVENTS}/${id}" > /dev/null
    echo "Tentative de suppression de l'événement de filtre: ${id}"
done

# Supprimer les événements de recherche
for id in "${EVENT_IDS_SEARCH[@]}"; do
    curl -s -X DELETE "${API_URL_EVENTS}/${id}" > /dev/null
    echo "Tentative de suppression de l'événement de recherche: ${id}"
done

check_success "Nettoyage final"


###############################################
print_header "RÉCAPITULATIF DES TESTS"
###############################################

echo -e "\n${GREEN}✓ Tests de base sur Events: Complétés${NC}"
echo -e "${GREEN}✓ Tests des cas d'erreur (Search & Events): Complétés${NC}"
echo -e "${GREEN}✓ Tests avec données complexes: Complétés${NC}"
echo -e "${GREEN}✓ Tests de filtrage et pagination (/v1/search): Complétés${NC}"
echo -e "${GREEN}✓ Tests de recherche vectorielle & hybride (/v1/search): Complétés${NC}"

echo -e "\n${GREEN}TOUS LES TESTS SONT TERMINÉS !${NC}"
echo -e "${BLUE}Vérifiez les messages ${RED}✗ Échec${BLUE} ci-dessus pour tout problème.${NC}" 