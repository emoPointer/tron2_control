import json
import uuid
import threading
import time
import websocket
from datetime import datetime

# Replace this ACCID value with your robot's actual serial number (SN)
ACCID = "DACH_TRON2A_003"

# Replace it with the real IP address of the robot. 
# for a real machine, it is: 10.192.1.2
ROBOT_IP = "10.192.1.2"

# Atomic flag for graceful exit
should_exit = False

# WebSocket client instance
ws_client = None

# Generate dynamic GUID
def generate_guid():
    return str(uuid.uuid4())

# Send WebSocket request with title and data
def send_request(title, data=None):
    global ACCID
    if data is None:
        data = {}
    
    # Create message structure with necessary fields
    message = {
        "accid": ACCID,
        "title": title,
        "timestamp": int(time.time() * 1000),  # Current timestamp in milliseconds
        "guid": generate_guid(),
        "data": data
    }

    message_str = json.dumps(message)
    
    # Send the message through WebSocket if client is connected
    if ws_client:
        ws_client.send(message_str)

# Handle user commands
def handle_commands():
    global should_exit
    while not should_exit:
        command = input("Enter command ('movej', 'movep', 'light', 'stop') or 'exit' to quit:\n")
        
        if command == "exit":
            should_exit = True  # Set exit flag to stop the loop
            break
        elif command == "movej":
            send_request("request_movej", { # request_movej
              "joint": [-0.5, 0.3, -0.2, 0.2, 0.2, 0.2, 0.2, -0.5, -0.3, -0.2, 0.2, 0.2, 0.2, 0.2],
              "time": 2
            }) 
        elif command == "movep":
            send_request("request_movep", { # request_movep
              "pos": [0.3, 0.2, -0.3, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0.3, -0.2, -0.3, 1, 0, 0, 0, 1, 0, 0, 0, 1],
              "time": 2
            })
        elif command == "light":
            send_request("request_light_effect", { # request_light_effect
              "effect": 2
            })
        elif command == "stop":
            send_request("request_emgy_stop", { # request_emgy_stop
            })

# WebSocket on_open callback
def on_open(ws):
    print("Connected!")
    # Start handling commands in a separate thread
    threading.Thread(target=handle_commands, daemon=True).start()

# WebSocket on_message callback
def on_message(ws, message):
    global ACCID
    root = json.loads(message)
    title = root.get("title", "")
    ACCID = root.get("accid", None)

    if title != "notify_robot_info":
        print(f"Received message: {message}")  # Print the received message

# WebSocket on_close callback
def on_close(ws, close_status_code, close_msg):
    print("Connection closed.")

# Close WebSocket connection
def close_connection(ws):
    ws.close()

def main():
    global ws_client
    
    # Create WebSocket client instance
    ws_client = websocket.WebSocketApp(
        f"ws://{ROBOT_IP}:5000",  # WebSocket server URI
        on_open=on_open,
        on_message=on_message,
        on_close=on_close
    )
    
    # Configure socket send and receive buffer sizes
    # Increase send buffer size to 2MB (default is typically much smaller)
    # This helps prevent data loss when sending large messages or high-frequency data
    ws_client.sock_opt = [("socket", "SO_SNDBUF", 2 * 1024 * 1024)]
    
    # Increase receive buffer size to 2MB
    # This allows handling larger incoming messages without truncation
    ws_client.sock_opt.append(("socket", "SO_RCVBUF", 2 * 1024 * 1024))
    
    # Run WebSocket client loop
    print("Press Ctrl+C to exit.")
    ws_client.run_forever()

if __name__ == "__main__":
    main()
