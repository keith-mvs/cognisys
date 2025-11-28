#!/bin/bash
# Post File Read Hook for IFMOS
# Automatically offers to classify documents when Claude reads unknown files

FILE_PATH="$1"
FILE_EXTENSION="${FILE_PATH##*.}"

# Check if this is a document type that IFMOS can classify
case "$FILE_EXTENSION" in
    pdf|docx|xlsx|txt|png|jpg|jpeg|html|py|ps1|yaml|json)
        # Check if file is in the inbox or unclassified directory
        if [[ "$FILE_PATH" == *"00_Inbox"* ]] || [[ "$FILE_PATH" == *"To_Review"* ]]; then
            echo "[IFMOS] This document appears to be unclassified. Would you like me to:"
            echo "  1. Classify it using the ML pipeline"
            echo "  2. Query similar documents in the database"
            echo "  3. Show classification statistics"
        fi
        ;;
esac

exit 0
