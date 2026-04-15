#!/usr/bin/env python3
"""
Tests unitaires et d'intégration pour l'auto-import des conversations.
EPIC-24: Auto-Save Conversations

Usage:
    EMBEDDING_MODE=mock pytest tests/test_conversation_import.py -v
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Import des fonctions à tester
import sys
sys.path.insert(0, '/app')

from routes.conversations_routes import parse_claude_transcripts


@pytest.fixture(autouse=True)
def _clean_dedup_state():
    """Remove deduplication state file before each test to prevent cross-test contamination."""
    state_file = Path("/tmp/mnemo-conversations-state.json")
    if state_file.exists():
        state_file.unlink()
    yield
    # Cleanup after test too
    if state_file.exists():
        state_file.unlink()


class TestConversationParsing:
    """Tests unitaires pour le parsing des transcripts Claude Code."""

    def test_parse_empty_directory(self, tmp_path):
        """Test avec un répertoire vide."""
        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))
        assert conversations == []

    def test_parse_simple_conversation(self, tmp_path):
        """Test avec une conversation simple user-assistant."""
        # Créer un transcript mock
        transcript_file = tmp_path / "test-session.jsonl"

        messages = [
            {
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Quelle est la capitale de la France?"}]
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "La capitale de la France est Paris."}]
                }
            }
        ]

        with open(transcript_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        # Make file appear older to bypass 120s cooldown filter
        import os
        os.utime(transcript_file, (transcript_file.stat().st_mtime - 130, transcript_file.stat().st_mtime - 130))

        # Parser
        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))

        # Vérifications
        assert len(conversations) == 1
        user_text, assistant_text, session_id, timestamp, project_name = conversations[0]
        assert "capitale de la France" in user_text
        assert "Paris" in assistant_text
        assert session_id == "test-session"

    def test_parse_with_thinking(self, tmp_path):
        """Test avec un message assistant contenant du thinking."""
        transcript_file = tmp_path / "thinking-session.jsonl"

        messages = [
            {
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "Calcule 2+2"}]
                }
            },
            {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "Je dois additionner 2 et 2"},
                        {"type": "text", "text": "2+2 = 4"}
                    ]
                }
            }
        ]

        with open(transcript_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        # Make file appear older to bypass 120s cooldown filter
        import os
        os.utime(transcript_file, (transcript_file.stat().st_mtime - 130, transcript_file.stat().st_mtime - 130))

        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))

        assert len(conversations) == 1
        user_text, assistant_text, session_id, timestamp, project_name = conversations[0]
        assert "Calcule" in user_text
        assert "2+2 = 4" in assistant_text
        assert "[Thinking:" in assistant_text  # Le thinking doit être inclus

    def test_parse_multiple_conversations(self, tmp_path):
        """Test avec plusieurs échanges user-assistant."""
        transcript_file = tmp_path / "multi-session.jsonl"

        messages = [
            {"message": {"role": "user", "content": [{"type": "text", "text": "Question 1"}]}},
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "Réponse 1"}]}},
            {"message": {"role": "user", "content": [{"type": "text", "text": "Question 2"}]}},
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "Réponse 2"}]}},
            {"message": {"role": "user", "content": [{"type": "text", "text": "Question 3"}]}},
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "Réponse 3"}]}},
        ]

        with open(transcript_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        # Make file appear older to bypass 120s cooldown filter
        import os
        os.utime(transcript_file, (transcript_file.stat().st_mtime - 130, transcript_file.stat().st_mtime - 130))

        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))

        assert len(conversations) == 3
        assert "Question 1" in conversations[0][0]
        assert "Réponse 1" in conversations[0][1]
        assert "Question 3" in conversations[2][0]
        assert "Réponse 3" in conversations[2][1]

    def test_deduplication(self, tmp_path):
        """Test que la déduplication fonctionne."""
        transcript_file = tmp_path / "dedup-session.jsonl"

        # Même conversation 2 fois
        messages = [
            {"message": {"role": "user", "content": [{"type": "text", "text": "Test dedup"}]}},
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "Response dedup"}]}},
        ] * 2  # Duplication

        with open(transcript_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        # Make file appear older to bypass 120s cooldown filter
        import os
        os.utime(transcript_file, (transcript_file.stat().st_mtime - 130, transcript_file.stat().st_mtime - 130))

        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))

        # Devrait n'avoir qu'une seule conversation (dédupliquée)
        assert len(conversations) == 1

    def test_skip_short_messages(self, tmp_path):
        """Test que les messages trop courts sont ignorés."""
        transcript_file = tmp_path / "short-session.jsonl"

        messages = [
            {"message": {"role": "user", "content": [{"type": "text", "text": "ok"}]}},  # Trop court
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
            {"message": {"role": "user", "content": [{"type": "text", "text": "Ceci est un message suffisamment long"}]}},
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "Voici une réponse suffisamment longue"}]}},
        ]

        with open(transcript_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        # Make file appear older to bypass 120s cooldown filter
        import os
        os.utime(transcript_file, (transcript_file.stat().st_mtime - 130, transcript_file.stat().st_mtime - 130))

        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))

        # Seule la 2ème conversation devrait être retenue
        assert len(conversations) == 1
        assert "suffisamment long" in conversations[0][0]

    def test_skip_agent_transcripts(self, tmp_path):
        """Test que les transcripts d'agents sont ignorés."""
        # Créer un transcript d'agent
        agent_file = tmp_path / "agent-12345.jsonl"
        agent_file.write_text('{"message": {"role": "user", "content": [{"type": "text", "text": "test"}]}}')

        # Créer un transcript normal
        normal_file = tmp_path / "normal-session.jsonl"
        messages = [
            {"message": {"role": "user", "content": [{"type": "text", "text": "Question normale"}]}},
            {"message": {"role": "assistant", "content": [{"type": "text", "text": "Réponse normale"}]}},
        ]

        with open(normal_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        # Make file appear older to bypass 120s cooldown filter
        import os
        os.utime(normal_file, (normal_file.stat().st_mtime - 130, normal_file.stat().st_mtime - 130))

        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))

        # Seul le transcript normal devrait être traité
        assert len(conversations) == 1
        assert "normale" in conversations[0][0]

    def test_malformed_json(self, tmp_path):
        """Test avec du JSON malformé."""
        transcript_file = tmp_path / "malformed-session.jsonl"

        with open(transcript_file, 'w') as f:
            f.write('{"invalid json\n')
            f.write('{"message": {"role": "user", "content": [{"type": "text", "text": "Valid message"}]}}\n')
            f.write('{"message": {"role": "assistant", "content": [{"type": "text", "text": "Valid response"}]}}\n')

        # Make file appear older to bypass 120s cooldown filter
        import os
        os.utime(transcript_file, (transcript_file.stat().st_mtime - 130, transcript_file.stat().st_mtime - 130))

        # Ne devrait pas crasher, juste ignorer les lignes invalides
        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))

        assert len(conversations) == 1


class TestConversationImportAPI:
    """Tests d'intégration pour l'API d'import."""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_save_endpoint_exists(self):
        """Test que l'endpoint /v1/conversations/save existe."""
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        # POST without required body params → should get 422 (validation error)
        # not 404 (endpoint not found)
        response = client.post("/v1/conversations/save")

        # 422 = endpoint exists but missing required params
        # 404 = endpoint doesn't exist
        assert response.status_code in (200, 422), f"Expected 200 or 422, got {response.status_code}"


class TestEndToEnd:
    """Tests end-to-end du système complet."""

    def test_full_workflow(self, tmp_path):
        """Test du workflow complet: parsing -> vérification."""
        # 1. Créer des transcripts réalistes
        transcript_file = tmp_path / "e2e-session.jsonl"

        conversations_data = [
            ("Quel est le but de MnemoLite?", "MnemoLite est un système de mémoire cognitive..."),
            ("Comment fonctionne la vectorisation?", "La vectorisation utilise des embeddings..."),
            ("Est-ce que les conversations sont sauvegardées?", "Oui, automatiquement via le daemon..."),
        ]

        messages = []
        for user_q, assistant_a in conversations_data:
            messages.append({
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": user_q}],
                    "timestamp": datetime.now().isoformat()
                }
            })
            messages.append({
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": f"Je dois répondre sur {user_q[:20]}..."},
                        {"type": "text", "text": assistant_a}
                    ],
                    "timestamp": datetime.now().isoformat()
                }
            })

        with open(transcript_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')

        # Make file appear older to bypass 120s cooldown filter
        import os
        os.utime(transcript_file, (transcript_file.stat().st_mtime - 130, transcript_file.stat().st_mtime - 130))

        # 2. Parser les conversations
        conversations = parse_claude_transcripts(projects_dir=str(tmp_path))

        # 3. Vérifications
        assert len(conversations) == 3, f"Expected 3 conversations, got {len(conversations)}"

        for i, (user_text, assistant_text, session_id, timestamp, project_name) in enumerate(conversations):
            expected_user, expected_assistant = conversations_data[i]

            assert expected_user in user_text, f"User text mismatch for conversation {i}"
            assert expected_assistant in assistant_text, f"Assistant text mismatch for conversation {i}"
            assert session_id == "e2e-session"
            assert timestamp  # Should have a timestamp


def test_print_summary():
    """Affiche un résumé des tests."""
    print("\n" + "="*80)
    print("📊 Résumé des Tests - Auto-Save Conversations (EPIC-24)")
    print("="*80)
    print("\n✅ Tests Unitaires:")
    print("  - Parsing de transcripts vides")
    print("  - Parsing de conversations simples")
    print("  - Gestion du contenu 'thinking'")
    print("  - Parsing de conversations multiples")
    print("  - Déduplication des conversations")
    print("  - Filtrage des messages trop courts")
    print("  - Exclusion des transcripts d'agents")
    print("  - Gestion du JSON malformé")
    print("\n✅ Tests d'Intégration:")
    print("  - Endpoint API /v1/conversations/import")
    print("\n✅ Tests End-to-End:")
    print("  - Workflow complet de parsing")
    print("\n" + "="*80)


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["pytest", __file__, "-v", "--tb=short"],
        env={"EMBEDDING_MODE": "mock"}
    )
    sys.exit(result.returncode)
