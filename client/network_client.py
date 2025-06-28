import socket
import threading
import json
import time
import config
import pygame

class NetworkClient:
    def __init__(self, app):
        self.app = app
        self.running = True
        self.polling_thread = None

    def connect(self):
        self.app.current_state = config.STATE_CONNECTING
        self.app.status_message = "Connecting to server..."
        
        connect_thread = threading.Thread(target=self._try_connect, daemon=True)
        connect_thread.start()

    def _try_connect(self):
        try:
            payload = json.dumps({"username": self.app.username})
            response_data = self.send_request('POST', '/connect', payload)
            
            if response_data and response_data.get("player_id"):
                self.app.player_id = response_data.get("player_id")
                self.app.current_state = config.STATE_GAME
                pygame.display.set_caption(f"Number Guess Game - {self.app.username}")
                self.app.player_usernames[self.app.player_id] = self.app.username
                # Polling because http
                self.start_polling()
            else:
                pass

        except Exception as e:
            self.app.handle_connection_error(f"Connection failed: {e}")

    def start_polling(self):
        self.polling_thread = threading.Thread(target=self.polling_loop, daemon=True)
        self.running = True
        self.polling_thread.start()

    def polling_loop(self):
        while self.running:
            try:
                if not self.app.player_id: # Don't poll if we don't have an ID
                    time.sleep(1)
                    continue
                headers = {"X-Player-ID": self.app.player_id}
                state_data = self.send_request('GET', '/gamestate', headers=headers)
                if state_data:
                    self.app.process_server_message({"type": "game_state", "data": state_data})
                else:
                    print("Polling failed, server might be down. Disconnecting.")
                    self.running = False
                time.sleep(1)
            except Exception as e:
                print(f"Error polling game state: {e}")
                self.running = False
        
        self.app.running = False

    def send_action(self, action_type, data={}):
        action_thread = threading.Thread(target=self._send_action_thread, args=(action_type, data), daemon=True)
        action_thread.start()
        
    def _send_action_thread(self, action_type, data):
        try:
            payload_dict = {"action": action_type, **data}
            payload_str = json.dumps(payload_dict)
            headers = {"X-Player-ID": self.app.player_id}
            response = self.send_request('POST', '/action', payload_str, headers)
            # After sending an action, immediately poll for the new state (no need to wait the full delay)
            if response:
                self.poll_once()
        except Exception as e:
            print(f"Failed to send action: {e}")

    def poll_once(self):
        try:
            headers = {"X-Player-ID": self.app.player_id}
            state_data = self.send_request('GET', '/gamestate', headers=headers)
            if state_data:
                self.app.process_server_message({"type": "game_state", "data": state_data})
        except Exception as e:
            print(f"Error during single poll: {e}")

    def send_request(self, method, path, body=None, headers={}):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.settimeout(10.0)
                client_socket.connect((config.SERVER_HOST, config.SERVER_PORT))
                
                request_line = f"{method} {path} HTTP/1.1\r\n"
                host_header = f"Host: {config.SERVER_HOST}:{config.SERVER_PORT}\r\n"
                
                final_headers = headers.copy()
                final_headers['Connection'] = 'close'

                if body:
                    final_headers['Content-Type'] = 'application/json'
                    final_headers['Content-Length'] = len(body.encode('utf-8'))
                
                header_lines = "".join([f"{k}: {v}\r\n" for k, v in final_headers.items()])
                
                header_block = request_line + host_header + header_lines
                request_str = header_block + "\r\n"
                if body:
                    request_str += body
                
                client_socket.sendall(request_str.encode('utf-8'))
                
                buffer = b""
                while True:
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        break
                    buffer += chunk

                if not buffer:
                    self.app.handle_connection_error("Received empty response from server.")
                    return None

                header_end_idx = buffer.find(b'\r\n\r\n')
                if header_end_idx == -1:
                    self.app.handle_connection_error("Invalid HTTP response (no header separator).")
                    return None
                    
                header_part = buffer[:header_end_idx]
                body_part = buffer[header_end_idx+4:]
                
                response_headers = header_part.decode('utf-8')
                response_line = response_headers.split('\r\n')[0]
                status_code = int(response_line.split(' ')[1])

                response_body = json.loads(body_part.decode('utf-8'))

                if status_code >= 400:
                    error_msg = response_body.get('error', 'Unknown server error')
                    print(f"Server Error (HTTP {status_code}): {error_msg}")
                    self.app.handle_connection_error(error_msg)
                    return None
                    
                return response_body

        except (socket.error, socket.timeout, ConnectionRefusedError, json.JSONDecodeError, IndexError) as e:
            self.app.handle_connection_error(f"Communication error: {e}")
            return None
        
    def close(self):
        self.running = False
        if self.app.player_id:
            disconnect_thread = threading.Thread(target=self._send_disconnect, daemon=True)
            disconnect_thread.start()
        
        if self.polling_thread and self.polling_thread.is_alive():
            self.polling_thread.join(timeout=1.0)
            
    def _send_disconnect(self):
        try:
            headers = {"X-Player-ID": self.app.player_id}
            self.send_request('POST', '/disconnect', headers=headers)
            print("Sent disconnect message to server.")
        except Exception as e:
            print(f"Failed to send disconnect message: {e}")

