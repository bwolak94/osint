#!/usr/bin/env bash
# Generate a .env file from .env.example with random secrets replacing placeholders.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
EXAMPLE_FILE="$PROJECT_ROOT/.env.example"
OUTPUT_FILE="$PROJECT_ROOT/.env"

if [ ! -f "$EXAMPLE_FILE" ]; then
    echo "Error: $EXAMPLE_FILE not found."
    exit 1
fi

if [ -f "$OUTPUT_FILE" ]; then
    echo "Warning: $OUTPUT_FILE already exists."
    read -rp "Overwrite? [y/N] " confirm
    if [ "$confirm" != "y" ]; then
        echo "Aborted."
        exit 0
    fi
fi

generate_secret() {
    openssl rand -base64 48 | tr -d '\n/+=' | head -c 64
}

generate_password() {
    openssl rand -base64 24 | tr -d '\n/+=' | head -c 32
}

cp "$EXAMPLE_FILE" "$OUTPUT_FILE"

# Replace secret placeholders with generated values
sed -i.bak "s|CHANGEME_GENERATE_A_RANDOM_SECRET|$(generate_secret)|g" "$OUTPUT_FILE"

# Replace each password placeholder individually so they get unique values
while grep -q "CHANGEME_GENERATE_A_RANDOM_PASSWORD" "$OUTPUT_FILE"; do
    sed -i.bak "0,/CHANGEME_GENERATE_A_RANDOM_PASSWORD/s||$(generate_password)|" "$OUTPUT_FILE"
done

# Clean up backup file created by sed
rm -f "$OUTPUT_FILE.bak"

echo "Generated $OUTPUT_FILE with random secrets."
