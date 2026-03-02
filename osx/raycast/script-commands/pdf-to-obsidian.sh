#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title PDF to Obsidian
# @raycast.mode fullOutput
# @raycast.packageName PDF Organizer

# Optional parameters:
# @raycast.icon 📄
# @raycast.description Extract PDF metadata with Claude AI and organize into Obsidian vault
# @raycast.argument1 { "type": "text", "placeholder": "filename filter", "optional": true }

set -euo pipefail

# Raycast runs in a minimal environment — set up PATH and API key
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
[[ -z "${ANTHROPIC_API_KEY:-}" && -f "$HOME/.zshenv.local" ]] && source "$HOME/.zshenv.local"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "Error: ANTHROPIC_API_KEY not set"
    echo "Add it to ~/.zshenv.local"
    exit 1
fi

DOWNLOADS_DIR="$HOME/Downloads"
VAULT_DIR="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian Vault"
REFERENCES_DIR="$VAULT_DIR/References"
MODEL="claude-sonnet-4-20250514"
API_URL="https://api.anthropic.com/v1/messages"
FILTER="${1:-}"

# Find PDFs in Downloads (sorted by modification time, newest first)
PDF_LIST=()
while IFS= read -r f; do
    PDF_LIST+=("$f")
done < <(
    if [[ -n "$FILTER" ]]; then
        find "$DOWNLOADS_DIR" -maxdepth 1 -iname "*${FILTER}*.pdf" -type f -print0 | xargs -0 ls -t 2>/dev/null
    else
        find "$DOWNLOADS_DIR" -maxdepth 1 -iname "*.pdf" -type f -print0 | xargs -0 ls -t 2>/dev/null | head -15
    fi
)

if [[ ${#PDF_LIST[@]} -eq 0 ]]; then
    echo "No PDFs found in $DOWNLOADS_DIR"
    exit 1
fi

# Select PDF
if [[ ${#PDF_LIST[@]} -eq 1 ]]; then
    SELECTED_PDF="${PDF_LIST[0]}"
else
    APPLESCRIPT_LIST=""
    for f in "${PDF_LIST[@]}"; do
        name=$(basename "$f")
        APPLESCRIPT_LIST+="\"$(echo "$name" | sed 's/"/\\"/g')\", "
    done
    APPLESCRIPT_LIST="${APPLESCRIPT_LIST%, }"

    CHOSEN=$(osascript -e "choose from list {${APPLESCRIPT_LIST}} with title \"PDF to Obsidian\" with prompt \"Select a PDF to organize:\"") || true

    if [[ "$CHOSEN" == "false" || -z "$CHOSEN" ]]; then
        echo "Cancelled"
        exit 0
    fi

    SELECTED_PDF="$DOWNLOADS_DIR/$CHOSEN"
fi

# Check file size (32MB API limit)
FILE_SIZE=$(stat -f%z "$SELECTED_PDF")
MAX_SIZE=$((32 * 1024 * 1024))
if [[ $FILE_SIZE -gt $MAX_SIZE ]]; then
    echo "Error: PDF exceeds 32MB API limit ($(( FILE_SIZE / 1024 / 1024 ))MB)"
    exit 1
fi

echo "Processing: $(basename "$SELECTED_PDF") ($(( FILE_SIZE / 1024 ))KB)..."

# Base64-encode to temp file (avoids shell argument length limits)
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT
base64 < "$SELECTED_PDF" | tr -d '\n' > "$TMPFILE"

# Build API request with jq --rawfile
PROMPT='Extract the bibliographic metadata from this PDF document.

1. author: Last name(s) of the author(s). Single author: "LastName". Two authors: "LastName1 and LastName2". Three or more: "FirstAuthor et al."
2. year: Publication year (4 digits)
3. title: Title of the paper/document

Respond with ONLY a JSON object, no other text:
{"author": "...", "year": "...", "title": "..."}'

REQFILE=$(mktemp)
trap 'rm -f "$TMPFILE" "$REQFILE"' EXIT

jq -n \
    --rawfile pdf_data "$TMPFILE" \
    --arg model "$MODEL" \
    --arg prompt "$PROMPT" \
    '{
        model: $model,
        max_tokens: 256,
        messages: [{
            role: "user",
            content: [
                {
                    type: "document",
                    source: {
                        type: "base64",
                        media_type: "application/pdf",
                        data: $pdf_data
                    }
                },
                {
                    type: "text",
                    text: $prompt
                }
            ]
        }]
    }' > "$REQFILE"

echo "Calling Claude API..."

RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL" \
    -H "content-type: application/json" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -d @"$REQFILE")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "API error (HTTP $HTTP_CODE):"
    echo "$BODY" | jq -r '.error.message // .' 2>/dev/null || echo "$BODY"
    exit 1
fi

# Parse metadata from response
CONTENT=$(echo "$BODY" | jq -r '.content[0].text')
CLEAN_JSON=$(echo "$CONTENT" | sed 's/^```json//; s/^```//; s/```$//' | tr -d '\n')

AUTHOR=$(echo "$CLEAN_JSON" | jq -r '.author // empty')
YEAR=$(echo "$CLEAN_JSON" | jq -r '.year // empty')
TITLE=$(echo "$CLEAN_JSON" | jq -r '.title // empty')

if [[ -z "$AUTHOR" || -z "$YEAR" || -z "$TITLE" ]]; then
    echo "Could not extract all metadata from Claude response:"
    echo "$CONTENT"
    exit 1
fi

PROPOSED_NAME="${AUTHOR} ${YEAR} - ${TITLE}.pdf"
echo "Extracted: $PROPOSED_NAME"

# Confirmation dialog with editable filename
ESCAPED_NAME=$(echo "$PROPOSED_NAME" | sed 's/\\/\\\\/g; s/"/\\"/g')
RESULT=$(osascript -e "
    set userInput to display dialog \"Proposed filename:\" default answer \"${ESCAPED_NAME}\" buttons {\"Cancel\", \"Save\"} default button \"Save\" with title \"PDF to Obsidian\"
    return text returned of userInput
") || true

if [[ -z "$RESULT" ]]; then
    echo "Cancelled"
    exit 0
fi

FINAL_NAME="$RESULT"
[[ "$FINAL_NAME" != *.pdf ]] && FINAL_NAME="${FINAL_NAME}.pdf"

# Copy PDF to vault
TARGET_PATH="$REFERENCES_DIR/$FINAL_NAME"
if [[ -f "$TARGET_PATH" ]]; then
    echo "Error: File already exists: $FINAL_NAME"
    exit 1
fi

mkdir -p "$REFERENCES_DIR"
cp "$SELECTED_PDF" "$TARGET_PATH"
echo "Copied: $FINAL_NAME"

# Create companion Obsidian markdown note
NOTE_NAME="${FINAL_NAME%.pdf}.md"
NOTE_PATH="$REFERENCES_DIR/$NOTE_NAME"

if [[ ! -f "$NOTE_PATH" ]]; then
    cat > "$NOTE_PATH" << MDEOF
---
author: "${AUTHOR}"
year: ${YEAR}
title: "${TITLE}"
---

# ${FINAL_NAME%.pdf}

![[${FINAL_NAME}]]
MDEOF
    echo "Created note: $NOTE_NAME"
fi

echo "Done!"
