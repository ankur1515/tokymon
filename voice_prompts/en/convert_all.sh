#!/bin/bash

# Tokymon voice prompt batch conversion
# Converts all MP3 files to WAV (PCM, 16-bit, Mono, 16kHz)

INPUT_DIR="/Users/ankursharma/Documents/Dev Projects/tokymon/voice_prompts/en"
OUTPUT_DIR="/Users/ankursharma/Documents/Dev Projects/tokymon/voice_prompts/en_wav"

mkdir -p "$OUTPUT_DIR"

for file in "$INPUT_DIR"/*.mp3; do
    if [ -f "$file" ]; then
        filename=$(basename "$file" .mp3)
        out="$OUTPUT_DIR/$filename.wav"

        echo "Converting: $file → $out"

        ffmpeg -y -loglevel error \
            -i "$file" \
            -ac 1 \
            -ar 16000 \
            -sample_fmt s16 \
            "$out"
    fi
done

echo "✅ All MP3 files converted to WAV successfully."