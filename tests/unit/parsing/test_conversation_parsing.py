#!/usr/bin/env python3
"""
Test script pour debugger le parsing des conversations Claude Code.
EPIC-24: Auto-Save Conversations - Debugging
"""

import json
from pathlib import Path

def test_parse_transcript():
    """Test parsing d'un transcript Claude Code."""

    # Path du transcript actuel
    transcript_file = Path("/home/user/.claude/projects/5906b2a1-cbd9-4d97-bc2b-81445d816ebe.jsonl")

    if not transcript_file.exists():
        print(f"❌ Transcript file not found: {transcript_file}")
        return

    print(f"✓ Transcript file found: {transcript_file}")
    print(f"  Size: {transcript_file.stat().st_size / 1024 / 1024:.2f} MB\n")

    # Parse JSONL
    messages = []
    line_count = 0
    parse_errors = 0

    with open(transcript_file, 'r', encoding='utf-8') as f:
        for line in f:
            line_count += 1
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)

                # Debug: afficher la structure du premier message
                if line_count == 1:
                    print("📋 Structure du premier message:")
                    print(f"  Keys: {list(msg.keys())}")
                    if 'message' in msg:
                        print(f"  message.keys: {list(msg['message'].keys())}")
                        if 'role' in msg['message']:
                            print(f"  message.role: {msg['message']['role']}")
                    print()

                # Claude Code format: {"message": {"role": "...", "content": ...}}
                if 'message' in msg and 'role' in msg['message']:
                    messages.append(msg['message'])

            except json.JSONDecodeError as e:
                parse_errors += 1
                if parse_errors <= 3:
                    print(f"⚠ JSON decode error at line {line_count}: {e}")

    print(f"📊 Parsing results:")
    print(f"  Total lines: {line_count}")
    print(f"  Parse errors: {parse_errors}")
    print(f"  Messages extracted: {len(messages)}")
    print()

    # Compter les rôles
    roles = {}
    for msg in messages:
        role = msg.get('role', 'unknown')
        roles[role] = roles.get(role, 0) + 1

    print(f"📈 Message roles:")
    for role, count in roles.items():
        print(f"  {role}: {count}")
    print()

    # Extract user-assistant pairs
    conversations = []
    i = 0
    while i < len(messages):
        if messages[i].get('role') == 'user':
            # Find next assistant message
            for j in range(i + 1, len(messages)):
                if messages[j].get('role') == 'assistant':
                    user_content = messages[i].get('content', '')
                    assistant_content = messages[j].get('content', '')

                    # Extract text from content (handle array format)
                    if isinstance(user_content, list):
                        user_text = '\n'.join([
                            item.get('text', '')
                            for item in user_content
                            if isinstance(item, dict) and item.get('type') == 'text'
                        ])
                    else:
                        user_text = str(user_content)

                    if isinstance(assistant_content, list):
                        assistant_text = '\n'.join([
                            item.get('text', '')
                            for item in assistant_content
                            if isinstance(item, dict) and item.get('type') == 'text'
                        ])
                    else:
                        assistant_text = str(assistant_content)

                    # Debug: afficher le premier échange
                    if len(conversations) == 0:
                        print(f"🔍 Premier échange trouvé:")
                        print(f"  User text length: {len(user_text)}")
                        print(f"  Assistant text length: {len(assistant_text)}")
                        print(f"  User preview: {user_text[:100]}...")
                        print(f"  Assistant preview: {assistant_text[:100]}...")
                        print()

                    # Skip if too short
                    if len(user_text) < 5 or len(assistant_text) < 5:
                        print(f"⚠ Skipping exchange (too short): user={len(user_text)} assistant={len(assistant_text)}")
                        i = j
                        break

                    conversations.append((user_text, assistant_text))
                    i = j
                    break
        i += 1

    print(f"✅ Total conversations extracted: {len(conversations)}")

    if conversations:
        print(f"\n📝 Sample conversation:")
        user, assistant = conversations[0]
        print(f"User: {user[:200]}...")
        print(f"Assistant: {assistant[:200]}...")


if __name__ == "__main__":
    test_parse_transcript()
