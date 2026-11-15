#!/usr/bin/env bash
# Helper script to send spectator chat advice into the running match

MSG="$*"
if [ -z "$MSG" ]; then
    echo "Usage: ./scripts/chat.sh <ข้อความแชทโค้ช>"
    echo "Example: ./scripts/chat.sh สวนหลังมันเลยลูกพี่"
    exit 1
fi

echo "$MSG" > /tmp/framewhisper_chat.txt
echo "✅ ส่งข้อความโค้ช: \"$MSG\" เข้าสู่เกมเรียบร้อย!"
