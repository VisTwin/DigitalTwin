import ollama
import sounddevice as sd
import numpy as np
import whisper

# Load the small Whisper model

 	
whisper_model = whisper.load_model("tiny.en")

# Function to record audio from the microphone
def record_audio(duration, sample_rate=16000):
    print("Recording...")
    audio_data = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
    sd.wait()
    return audio_data

# Function to convert audio to text using Whisper
def audio_to_text(audio_data, sample_rate=16000):
    audio_data = audio_data.flatten()
    print("Transcribing...")
    transcription = whisper_model.transcribe(audio_data, language="en")
    return transcription['text']

# Main loop for the voice chat; error portion
def voice_chat():
    print("Voice chat started. Say something. Type 'exit' to quit.")
    while True:
        # Record a short audio clip
        audio_input = record_audio(duration=10)  # Records for 10 seconds

        # Transcribe the audio
        user_text = audio_to_text(audio_input)
        print(f"You: {user_text}") 

        if "exit" in user_text.lower():
            print("Exiting.")
            break

        
        # Send transcribed text to Ollama
        response = ollama.chat(
            model='gemma3',
            messages=[{'role': 'user', 'content': user_text}],

            stream=False
        )

        # Print the streaming response from Gemma 3
        print("Gemma 3:", end=" ")
        #for chunk in response:
            #print(chunk['message']['content'], end="")
        print(response['message']['content'])

if __name__ == "__main__":
    voice_chat()
