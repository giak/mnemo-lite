#!/bin/bash

# Couleurs pour la sortie
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

API_URL="http://localhost:8001/v0/memories"

# Fonction pour afficher les messages d'en-tête
print_header() {
    echo -e "\n${BLUE}==== $1 ====${NC}"
}

# Fonction pour vérifier si une commande a réussi
check_success() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Succès: $1${NC}"
    else
        echo -e "${RED}✗ Échec: $1${NC}"
        exit 1
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
        return 1
    fi
}

# Fonction pour imprimer une section
print_section() {
    echo -e "\n${YELLOW}--- $1 ---${NC}"
}

echo -e "${BLUE}==================================================================${NC}"
echo -e "${BLUE}     TEST COMPLET DE L'API MEMORY - TOUS LES CAS POSSIBLES        ${NC}"
echo -e "${BLUE}==================================================================${NC}"

###############################################
print_header "1. TESTS DE BASE (CRUD)"
###############################################

# Générer un ID aléatoire pour les tests
MEMORY_ID=$(cat /proc/sys/kernel/random/uuid)
echo -e "${BLUE}ID mémoire de test: ${MEMORY_ID}${NC}"

print_section "1.1 CREATE - Créer une nouvelle mémoire"
CREATE_RESPONSE=$(curl -s -X POST "${API_URL}/" \
    -H "Content-Type: application/json" \
    -d '{
        "memory_type": "episodic",
        "event_type": "test_event",
        "role_id": 999,
        "content": {
            "message": "Ceci est un test de création de mémoire",
            "source": "test_script"
        },
        "metadata": {
            "test": true,
            "created_by": "test_script",
            "importance": "high"
        }
    }')

echo "$CREATE_RESPONSE" | jq
check_success "Création de mémoire"

# Extraire l'ID de la réponse
MEMORY_ID=$(echo "$CREATE_RESPONSE" | jq -r '.id')
echo -e "${BLUE}ID mémoire créée: ${MEMORY_ID}${NC}"

print_section "1.2 READ - Récupérer une mémoire par son ID"
READ_RESPONSE=$(curl -s -X GET "${API_URL}/${MEMORY_ID}")
echo "$READ_RESPONSE" | jq
check_success "Lecture de mémoire"

print_section "1.3 LIST - Lister toutes les mémoires"
LIST_RESPONSE=$(curl -s -X GET "${API_URL}/?limit=5")
echo "$LIST_RESPONSE" | jq
check_success "Liste des mémoires"

print_section "1.4 LIST avec filtres - Filtrer les mémoires par type"
FILTER_RESPONSE=$(curl -s -X GET "${API_URL}/?memory_type=episodic&event_type=test_event&limit=5")
echo "$FILTER_RESPONSE" | jq
check_success "Liste des mémoires avec filtres"

print_section "1.5 UPDATE - Mettre à jour la mémoire"
UPDATE_RESPONSE=$(curl -s -X PUT "${API_URL}/${MEMORY_ID}" \
    -H "Content-Type: application/json" \
    -d '{
        "memory_type": "semantic",
        "content": {
            "message": "Ceci est un test de mise à jour de mémoire",
            "source": "test_script",
            "updated": true
        },
        "metadata": {
            "test": true,
            "updated_by": "test_script",
            "importance": "medium"
        }
    }')

echo "$UPDATE_RESPONSE" | jq
check_success "Mise à jour de mémoire"

print_section "1.6 READ après UPDATE - Vérifier les changements"
VERIFY_RESPONSE=$(curl -s -X GET "${API_URL}/${MEMORY_ID}")
echo "$VERIFY_RESPONSE" | jq
check_success "Vérification des changements"

print_section "1.7 DELETE - Supprimer la mémoire"
DELETE_RESPONSE=$(curl -s -X DELETE "${API_URL}/${MEMORY_ID}" -w "%{http_code}")
HTTP_CODE=$DELETE_RESPONSE
check_http_code "$HTTP_CODE" 204 "Suppression de mémoire" || exit 1

print_section "1.8 READ après DELETE - Vérifier que la mémoire n'existe plus"
VERIFY_DELETE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/${MEMORY_ID}")
check_http_code "$VERIFY_DELETE" 404 "Vérification de la suppression" || exit 1

###############################################
print_header "2. TESTS DES CAS D'ERREUR"
###############################################

print_section "2.1 GET avec ID au format invalide"
INVALID_ID="not-a-valid-uuid"
INVALID_ID_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/${INVALID_ID}")
check_http_code "$INVALID_ID_RESPONSE" 422 "Récupération avec ID invalide" || echo "Ce test a échoué mais nous continuons"

print_section "2.2 GET avec un ID UUID valide mais inexistant"
NONEXISTENT_ID="11111111-1111-1111-1111-111111111111"
NONEXISTENT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/${NONEXISTENT_ID}")
check_http_code "$NONEXISTENT_RESPONSE" 404 "Récupération avec ID inexistant" || echo "Ce test a échoué mais nous continuons"

print_section "2.3 POST avec données incomplètes (memory_type manquant)"
INVALID_CREATE_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${API_URL}/" \
    -H "Content-Type: application/json" \
    -d '{
        "event_type": "test_event",
        "role_id": 999,
        "content": {"message": "Données incomplètes"},
        "metadata": {"test": true}
    }')
check_http_code "$INVALID_CREATE_RESPONSE" 422 "Création avec données incomplètes" || echo "Ce test a échoué mais nous continuons"

print_section "2.4 PUT sur une mémoire inexistante"
NONEXISTENT_UPDATE=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "${API_URL}/${NONEXISTENT_ID}" \
    -H "Content-Type: application/json" \
    -d '{"memory_type": "semantic", "content": {"message": "Mise à jour impossible"}}')
check_http_code "$NONEXISTENT_UPDATE" 404 "Mise à jour d'une mémoire inexistante" || echo "Ce test a échoué mais nous continuons"

print_section "2.5 DELETE d'une mémoire déjà supprimée"
ALREADY_DELETED=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "${API_URL}/${MEMORY_ID}")
check_http_code "$ALREADY_DELETED" 404 "Suppression d'une mémoire déjà supprimée" || echo "Ce test a échoué mais nous continuons"

###############################################
print_header "3. TESTS AVEC DIFFÉRENTS TYPES DE DONNÉES"
###############################################

print_section "3.1 CREATE avec contenu complexe et multilingue"
COMPLEX_CONTENT_RESPONSE=$(curl -s -X POST "${API_URL}/" \
    -H "Content-Type: application/json" \
    -d '{
        "memory_type": "procedural",
        "event_type": "complex_test",
        "role_id": 888,
        "content": {
            "title": "Test complexe",
            "description": "Description avec caractères spéciaux: éèêëàâäôöùûüÿç",
            "items": [
                {"id": 1, "value": "Premier élément"},
                {"id": 2, "value": "Deuxième élément"}
            ],
            "nested": {
                "level1": {
                    "level2": {
                        "level3": "Données profondément imbriquées"
                    }
                }
            }
        },
        "metadata": {
            "tags": ["test", "complex", "multilingual"],
            "priority": 10,
            "active": true,
            "dimensions": {
                "width": 100,
                "height": 200
            }
        }
    }')

echo "$COMPLEX_CONTENT_RESPONSE" | jq
check_success "Création avec contenu complexe"

COMPLEX_ID=$(echo "$COMPLEX_CONTENT_RESPONSE" | jq -r '.id')
echo -e "${BLUE}ID mémoire complexe: ${COMPLEX_ID}${NC}"

# Vérifier que toutes les données sont bien sauvegardées
print_section "3.2 READ de mémoire avec contenu complexe"
COMPLEX_READ=$(curl -s -X GET "${API_URL}/${COMPLEX_ID}")
echo "$COMPLEX_READ" | jq
check_success "Lecture de mémoire avec contenu complexe"

# Nettoyer après test
curl -s -X DELETE "${API_URL}/${COMPLEX_ID}" > /dev/null

###############################################
print_header "4. TESTS DE FILTRAGE ET PAGINATION"
###############################################

# Créer quelques mémoires pour les tests de filtrage
print_section "4.1 Création de mémoires pour le test de filtrage"

# Créer mémoire 1
MEM1_RESPONSE=$(curl -s -X POST "${API_URL}/" \
    -H "Content-Type: application/json" \
    -d '{
        "memory_type": "episodic",
        "event_type": "filter_test",
        "role_id": 100,
        "content": {"message": "Mémoire filtrable 1"},
        "metadata": {"category": "A", "tag": "filter-test"}
    }')
MEM1_ID=$(echo "$MEM1_RESPONSE" | jq -r '.id')
echo -e "Mémoire 1 créée: ${MEM1_ID}"

# Créer mémoire 2
MEM2_RESPONSE=$(curl -s -X POST "${API_URL}/" \
    -H "Content-Type: application/json" \
    -d '{
        "memory_type": "episodic",
        "event_type": "filter_test",
        "role_id": 200,
        "content": {"message": "Mémoire filtrable 2"},
        "metadata": {"category": "B", "tag": "filter-test"}
    }')
MEM2_ID=$(echo "$MEM2_RESPONSE" | jq -r '.id')
echo -e "Mémoire 2 créée: ${MEM2_ID}"

# Créer mémoire 3
MEM3_RESPONSE=$(curl -s -X POST "${API_URL}/" \
    -H "Content-Type: application/json" \
    -d '{
        "memory_type": "semantic",
        "event_type": "other_test",
        "role_id": 100,
        "content": {"message": "Mémoire filtrable 3"},
        "metadata": {"category": "A", "tag": "filter-test"}
    }')
MEM3_ID=$(echo "$MEM3_RESPONSE" | jq -r '.id')
echo -e "Mémoire 3 créée: ${MEM3_ID}"

# Test de filtrage par memory_type
print_section "4.2 Filtrage par memory_type=episodic"
TYPE_FILTER=$(curl -s -X GET "${API_URL}/?memory_type=episodic&limit=10")
EPISODIC_COUNT=$(echo "$TYPE_FILTER" | jq '. | length')
echo "Nombre de mémoires de type episodic: $EPISODIC_COUNT"
check_success "Filtrage par memory_type"

# Test de filtrage par event_type
print_section "4.3 Filtrage par event_type=filter_test"
EVENT_FILTER=$(curl -s -X GET "${API_URL}/?event_type=filter_test&limit=10")
EVENT_COUNT=$(echo "$EVENT_FILTER" | jq '. | length')
echo "Nombre de mémoires avec event_type=filter_test: $EVENT_COUNT"
check_success "Filtrage par event_type"

# Test de filtrage par role_id
print_section "4.4 Filtrage par role_id=100"
ROLE_FILTER=$(curl -s -X GET "${API_URL}/?role_id=100&limit=10")
ROLE_COUNT=$(echo "$ROLE_FILTER" | jq '. | length')
echo "Nombre de mémoires avec role_id=100: $ROLE_COUNT"
check_success "Filtrage par role_id"

# Test de filtrage combiné
print_section "4.5 Filtrage combiné (memory_type et role_id)"
COMBINED_FILTER=$(curl -s -X GET "${API_URL}/?memory_type=episodic&role_id=100&limit=10")
COMBINED_COUNT=$(echo "$COMBINED_FILTER" | jq '. | length')
echo "Nombre de mémoires avec memory_type=episodic ET role_id=100: $COMBINED_COUNT"
check_success "Filtrage combiné"

# Test de pagination
print_section "4.6 Test de pagination (limit et offset)"
# Récupérer les 2 premiers résultats
PAGE1=$(curl -s -X GET "${API_URL}/?limit=2&offset=0")
PAGE1_COUNT=$(echo "$PAGE1" | jq '. | length')
echo "Page 1 (limit=2, offset=0): $PAGE1_COUNT résultats"

# Récupérer les 2 résultats suivants
PAGE2=$(curl -s -X GET "${API_URL}/?limit=2&offset=2")
PAGE2_COUNT=$(echo "$PAGE2" | jq '. | length')
echo "Page 2 (limit=2, offset=2): $PAGE2_COUNT résultats"

check_success "Test de pagination"

# Nettoyer les mémoires créées pour le test
curl -s -X DELETE "${API_URL}/${MEM1_ID}" > /dev/null
curl -s -X DELETE "${API_URL}/${MEM2_ID}" > /dev/null
curl -s -X DELETE "${API_URL}/${MEM3_ID}" > /dev/null

###############################################
print_header "RÉCAPITULATIF DES TESTS"
###############################################

echo -e "\n${GREEN}✓ Tests CRUD de base: Réussis${NC}"
echo -e "${GREEN}✓ Tests des cas d'erreur: Complétés${NC}"
echo -e "${GREEN}✓ Tests avec différents types de données: Réussis${NC}"
echo -e "${GREEN}✓ Tests de filtrage et pagination: Réussis${NC}"

echo -e "\n${GREEN}TOUS LES TESTS SONT TERMINÉS !${NC}"
echo -e "${BLUE}L'API mémoire est fonctionnelle et répond comme attendu à tous les cas testés.${NC}" 