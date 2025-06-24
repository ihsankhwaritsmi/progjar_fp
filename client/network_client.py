# network_client.py

import socket
import threading
import json
import config

class NetworkClient:
    def __init__(self, app):
        self.app = app
        self.client_socket = None
        self.running = True

    def connect(self):
        self.app.current_state = config.STATE_CONNECTING
        self.app.status_message = "Connecting to server..."
        
        network_thread = threading.Thread(target=self.network_loop, daemon=True)
        network_thread.start()

    def network_loop(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((config.SERVER_HOST, config.SERVER_PORT))
            
            # Send username
            welcome_message = {"username": self.app.username}
            self.send(welcome_message)
            
        except (socket.error, ConnectionRefusedError) as e:
            self.app.handle_connection_error(f"Connection failed: {e}")
            return
            
        buffer = ""
        while self.running:
            try:
                data = self.client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    message_str, buffer = buffer.split('\n', 1)
                    if message_str:
                        self.handle_server_message(message_str)
            except (socket.error, ConnectionResetError):
                break
        
        print("Disconnected from server.")
        self.running = False
        self.app.running = False # Signal main app to close

    def handle_server_message(self, message_str):
        try:
            message = json.loads(message_str)
            self.app.process_server_message(message)
        except json.JSONDecodeError:
            print(f"Received invalid JSON: {message_str}")

    def send(self, data):
        if not self.client_socket or not self.running:
            return
        try:
            message = json.dumps(data) + '\n'
            self.client_socket.sendall(message.encode('utf-8'))
        except socket.error as e:
            print(f"Failed to send action: {e}")
            self.running = False

    def send_action(self, action_type, data={}):
        payload = {"action": action_type, **data}
        self.send(payload)
        
    def close(self):
        self.running = False
        if self.client_socket:
            self.client_socket.close()