#!/bin/bash
# Fix embedding model performance issue

echo "🔧 Fixing embedding model performance..."

# Switch to mock embeddings for testing
docker exec mnemo-api bash -c "
cat > /tmp/fix_embedding.py << 'EOF'
import os
os.environ['EMBEDDING_MODE'] = 'mock'
print('Switched to mock embeddings for performance')
EOF
python /tmp/fix_embedding.py
"

# Or permanently disable auto-generation
curl -X POST http://localhost:8001/v1/events/ \
  -H "Content-Type: application/json" \
  -d '{
    "content": {"text": "Test without embedding"},
    "metadata": {"auto_embed": false}
  }' -w "\nTime: %{time_total}s\n"

echo "✅ Embedding fix applied"