import os
import time

def speak(text):
    print("Speaking:", text)
    os.system(f'espeak "{text}" --stdout | aplay -D plughw:2,0')

def beep():
    print("Beep test (Left & Right)…")
    # Left speaker
    os.system('speaker-test -t sine -f 600 -c 2 -s 1 -D plughw:2,0 -l 1')
    time.sleep(1)
    # Right speaker
    os.system('speaker-test -t sine -f 600 -c 2 -s 2 -D plughw:2,0 -l 1')

print("\n🔊 Tokymon Audio System Test Starting...\n")

# Tokymon intro
speak("Hello, I am Tokymon.")
time.sleep(1)
speak("Your smart companion and friend.")
time.sleep(1)
speak("Testing my speakers now.")

# Speaker test
beep()

print("\n✅ Audio Test Completed!\n")