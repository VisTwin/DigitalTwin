# voice_joint_control_improved.py
import os
import time
import warnings
import re
import speech_recognition as sr
from word2number import w2n
from xarm.wrapper import XArmAPI

# ================= CONFIG =================
ROBOT_IP = "192.168.1.152"  # Replace with your xArm IP
NUM_JOINTS = 6
DEFAULT_MIC_INDEX = None      # None = default mic
SPEECH_TIMEOUT = 5            # seconds to wait for phrase
PHRASE_LIMIT = 6              # seconds max phrase length
# ==========================================

# --- Suppress ALSA warnings ---
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.filterwarnings("ignore", category=UserWarning, module='speech_recognition')

# --- Connect to xArm ---
print("Connecting to xArm...")
arm = XArmAPI(ROBOT_IP)
arm.connect()
try:
    arm.clean_warn()
    arm.clean_error()
    arm.motion_enable(True)
    arm.set_mode(0)  # Position control
    arm.set_state(0) # Ready
except Exception as e:
    print("Warning: could not fully initialize arm:", e)
time.sleep(0.5)

# Initialize all joints to 0
try:
    arm.set_servo_angle(servo_id=None, angle=[0]*NUM_JOINTS, is_radian=False)
except Exception as e:
    print("Warning: initial set_servo_angle failed:", e)

print("xArm connected and initialized.")

# --- Speech recognizer ---
recognizer = sr.Recognizer()

# List available microphones
def list_mics():
    names = sr.Microphone.list_microphone_names()
    print("\nAvailable microphones:")
    for i, name in enumerate(names):
        print(f"  {i}: {name}")
    return names

mics = list_mics()

# Choose mic
if DEFAULT_MIC_INDEX is None:
    mic_index = 24
else:
    mic_index = DEFAULT_MIC_INDEX
print(f"Using microphone index {mic_index}.")

# --- Move joint safely ---
def move_joint(joint_num, angle):
    if 1 <= joint_num <= NUM_JOINTS:
        try:
            current_angles = arm.get_servo_angle()[1][:NUM_JOINTS]
            current_angles[joint_num - 1] = angle
            arm.set_servo_angle(servo_id=None, angle=current_angles, is_radian=False)
            print(f"[OK] Joint {joint_num} -> {angle}°")
        except Exception as e:
            print("Error moving joint:", e)
            try:
                arm.stop()
                arm.clear_alarm()
                arm.clean_warn()
                arm.clean_error()
                arm.motion_enable(True)
                arm.set_mode(0)
                arm.set_state(0)
                print("Recovery attempted.")
            except:
                print("Recovery failed.")
    else:
        print(f"Invalid joint number: {joint_num}")

# --- Parse voice command ---
def parse_joint_command(command):
    command = command.lower().replace("join", "joint")  # fix mishearing
    match = re.search(r"joint (\d+) to (\d+)", command)
    if match:
        return int(match.group(1)), int(match.group(2))
    else:
        # Parse numbers as words too
        nums = re.findall(r"\b\w+\b", command)
        numbers = []
        for n in nums:
            try:
                numbers.append(int(n))
            except:
                try:
                    numbers.append(w2n.word_to_num(n))
                except:
                    continue
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
    return None, None

# --- Main loop ---
try:
    while True:
        try:
            with sr.Microphone(device_index=mic_index) as source:
                print("\nListening (say e.g. 'move joint 2 to 45')...")
                recognizer.adjust_for_ambient_noise(source) 
               
                
            
                audio = recognizer.listen(source, timeout=SPEECH_TIMEOUT, phrase_time_limit=PHRASE_LIMIT)

            command = recognizer.recognize_google(audio).lower()
            print("Heard:", command)

            if any(x in command for x in ["move joint", "joint"]):
                joint_num, angle = parse_joint_command(command)
                if joint_num is not None and angle is not None:
                    move_joint(joint_num, angle)
                else:
                    print("Could not parse command. Example: 'move joint 1 to 30'")
            elif any(x in command for x in ["stop", "exit", "quit"]):
                print("Exit command received. Stopping...")
                break
            else:
                print("Command not recognized. Use format: 'move joint 1 to 30'")

        except sr.WaitTimeoutError:
            print("Listening timed out. Retrying...")
        except sr.UnknownValueError:
            print("Could not understand speech. Try again...")
        except sr.RequestError as e:
            print(f"Speech recognition error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

except KeyboardInterrupt:
    print("\nKeyboard interrupt detected, exiting...")

finally:
    print("Returning to home position and disconnecting...")
    for i in range(1, NUM_JOINTS+1):
        move_joint(i, 0)
        time.sleep(0.3)
    arm.motion_enable(False)
    arm.disconnect()
    print("Done. Goodbye.")
