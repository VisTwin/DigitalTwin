import requests
import speech_recognition as sr

# Webhook URL from Pushcut or Shortcuts Remote
SHORTCUT_URLS = {
    #replace links with ones from the shortcuts app 
    "takeoff": "https://api.pushcut.io/<your_device_id>/takeoff",
    "land": "https://api.pushcut.io/<your_device_id>/land"
}

r = sr.Recognizer()
mic = sr.Microphone()
#Bridge from ollama code to dji flylink app on ipad
print("Say a command: (take off / land)")

while True:
    with mic as source:
        audio = r.listen(source)
    try:
        cmd = r.recognize_google(audio).lower()
        print(f"You said: {cmd}")

        if "take off" in cmd:
            print("Sending takeoff command to iPad...")
            requests.get(SHORTCUT_URLS["takeoff"])
        elif "land" in cmd:
            print("Sending land command to iPad...")
            requests.get(SHORTCUT_URLS["land"])
        else:
            print("Command not recognized.")
    except Exception as e:
        print("Error:", e)
