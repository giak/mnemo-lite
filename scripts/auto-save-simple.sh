#!/bin/bash
# Auto-save conversations - VERSION ULTRA SIMPLE
# Parse le transcript actif toutes les 10s et sauvegarde nouveaux échanges

TRANSCRIPT_DIR="$HOME/.claude/projects/-home-giak-Work-MnemoLite"
STATE_FILE="/tmp/mnemo-autosave-state.txt"
HASH_FILE="/tmp/mnemo-saved-exchanges.txt"

touch "$STATE_FILE" "$HASH_FILE"

echo "[$(date)] Auto-save daemon started"

while true; do
    # Trouver le transcript le plus récent (session active)
    CURRENT_TRANSCRIPT=$(ls -t "$TRANSCRIPT_DIR"/*.jsonl 2>/dev/null | grep -v "agent-" | head -1)

    if [ -z "$CURRENT_TRANSCRIPT" ]; then
        sleep 10
        continue
    fi

    # Parser les échanges user+assistant
    tail -100 "$CURRENT_TRANSCRIPT" | jq -s '
        [.[] | select(.role == "user" or .role == "assistant")] |
        reduce .[] as $msg (
            {pairs: [], current: null};
            if $msg.role == "user" then
                .current = $msg
            elif $msg.role == "assistant" and .current != null then
                .pairs += [{
                    user: (if (.current.content | type) == "array" then
                        [.current.content[] | select(.type == "text") | .text] | join("\n")
                    else .current.content end),
                    assistant: (if ($msg.content | type) == "array" then
                        [$msg.content[] | select(.type == "text") | .text] | join("\n")
                    else $msg.content end)
                }] | .current = null
            else . end
        ) | .pairs[]
    ' 2>/dev/null | while read -r pair; do
        USER=$(echo "$pair" | jq -r '.user // ""')
        ASSISTANT=$(echo "$pair" | jq -r '.assistant // ""')

        # Skip si trop court
        [ ${#USER} -lt 5 ] && continue
        [ ${#ASSISTANT} -lt 5 ] && continue

        # Hash pour dedup
        HASH=$(echo -n "${USER}${ASSISTANT}" | md5sum | cut -d' ' -f1 | cut -c1-16)

        # Skip si déjà sauvé
        grep -q "^${HASH}$" "$HASH_FILE" 2>/dev/null && continue

        # Sauvegarder
        docker compose -f /home/giak/Work/MnemoLite/docker-compose.yml exec -T api \
            python3 /app/.claude/hooks/Stop/save-direct.py \
            "$USER" \
            "$ASSISTANT" \
            "auto_$(date +%Y%m%d)" \
            2>&1 | grep -E "^[✓✗]" || true

        # Marquer comme sauvé
        echo "$HASH" >> "$HASH_FILE"
        echo "[$(date)] Saved exchange (hash: $HASH)"
    done

    sleep 10
done
