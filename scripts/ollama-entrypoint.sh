#!/bin/sh
set -e

READY_FILE="/tmp/ollama-ready"
rm -f "$READY_FILE"

# Start Ollama server in the background
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
until ollama list > /dev/null 2>&1; do
  sleep 1
done
echo "Ollama is ready."

# Pull required models (skips if already cached in the volume)
for model in "qwen2.5:7b-instruct" "deepseek-r1:7b" "bge-m3:latest"; do
  echo "Pulling model: $model ..."
  ollama pull "$model"
  echo "Model $model ready."
done

echo "All models loaded. Ollama is running."
touch "$READY_FILE"

# Bring Ollama back to the foreground so Docker can track the process
wait $OLLAMA_PID
