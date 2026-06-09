#!/bin/bash

FILE="PROPOSAL.md"
COMMAND="make PROPOSAL.html PROPOSAL.pdf"

# Check if the file exists before starting
if [ ! -f "$FILE" ]; then
    echo "Error: $FILE not found!"
    exit 1
fi

# Get the initial checksum
LAST_CHKSUM=$(cksum "$FILE" | awk '{print $1}')

echo "Watching $FILE for changes..."

while true; do
    # Pause for 1 second between checks to save CPU cycles
    sleep 1

    # Get the current checksum
    CURRENT_CHKSUM=$(cksum "$FILE" | awk '{print $1}')

    # If the checksum has changed, run the make command
    if [ "$LAST_CHKSUM" != "$CURRENT_CHKSUM" ]; then
        echo "------------------------------------------------"
        echo "📝 Change detected at $(date '+%H:%M:%S')!"
        echo "⚙️  Running: $COMMAND"

        $COMMAND

        # Update the checksum to the new state
        LAST_CHKSUM=$CURRENT_CHKSUM

        echo "👀 Watching for new changes..."
    fi
done
