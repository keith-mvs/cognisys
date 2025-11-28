#!/bin/bash
# User Prompt Submit Hook
# Detects classification correction requests and captures feedback

USER_PROMPT="$1"

# Detect feedback patterns like "this should be classified as X" or "incorrect classification"
if echo "$USER_PROMPT" | grep -iE "(should be classified|incorrect classification|wrong type|actually.*document)" > /dev/null; then
    echo "[IFMOS Feedback] Detected potential classification feedback."
    echo "I'll capture this feedback to improve the model."
fi

# Detect batch processing queries
if echo "$USER_PROMPT" | grep -iE "(batch.*status|processing.*progress|how many.*classified)" > /dev/null; then
    echo "[IFMOS Monitor] Checking batch processing status..."

    # Get current count from ML database
    RESULT_COUNT=$(find ~/ml_batch_results -name "doc_*.json" 2>/dev/null | wc -l)
    echo "[IFMOS Monitor] Processed $RESULT_COUNT documents so far."
fi

exit 0
