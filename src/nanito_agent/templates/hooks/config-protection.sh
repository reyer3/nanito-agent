#!/bin/bash
# Hook: config-protection
# Prevents accidental modification of linter/formatter/CI configs
# Exit code 2 = hard block

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

PROTECTED_PATTERNS=(
  ".eslintrc" ".prettierrc" "biome.json" "biome.jsonc"
  ".ruff.toml" "ruff.toml" "pyproject.toml"
  ".flake8" "setup.cfg"
  "tsconfig.json"
  ".github/workflows"
  "Dockerfile" "docker-compose.yml"
)

for pattern in "${PROTECTED_PATTERNS[@]}"; do
  if echo "$FILE_PATH" | grep -q "$pattern"; then
    echo "WARNING: Modifying protected config file: $FILE_PATH. Confirm this is intentional." >&2
    exit 0  # warn but allow (exit 2 would block)
  fi
done

exit 0
