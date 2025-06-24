# file: client_handler.py

import threading
import socket
import json
import uuid
import logging

class ClientHandler(threading.Thread):
    """Handles communication with a single client."""
    def __init__(self, connection, address, game_instance, clients_dict, lock):
        super().__init__()
        self.connection = connection
        self.address = address
        self.game = game_instance
        self.clients = clients_dict
        self.lock = lock
        self.player_id = f"player_{uuid.uuid4().hex[:6]}"
        self.username = self.player_id

    def run(self):
        logging.info(f"Processing connection from {self.address} for {self.player_id}")
        try:
            self._register_client()
            self._message_loop()
        except Exception as e:
            logging.error(f"An unexpected error occurred with client {self.username}: {e}")
        finally:
            self._cleanup()
    
    def _register_client(self):
        """Receives username and adds player to the game."""
        buffer = ""
        while '\n' not in buffer:
            data = self.connection.recv(4096)
            if not data: raise ConnectionAbortedError("Client disconnected before sending username.")
            buffer += data.decode('utf-8')
        
        message, _ = buffer.split('\n', 1)
        welcome_data = json.loads(message)
        self.username = welcome_data.get("username", self.player_id)

        join_result = self.game.add_player(self.player_id, self.username)
        if join_result.get("status") == "error":
            error_msg = json.dumps({"type": "error", "message": join_result["message"]}) + '\n'
            self.connection.sendall(error_msg.encode('utf-8'))
            raise ValueError(join_result["message"]) # Stop thread execution

        with self.lock:
            self.clients[self.connection] = self.player_id
        
        welcome_msg = json.dumps({"type": "welcome", "player_id": self.player_id}) + '\n'
        self.connection.sendall(welcome_msg.encode('utf-8'))
        self.broadcast_state()

    def _message_loop(self):
        """Continuously listens for and processes client messages."""
        buffer = ""
        while True:
            data = self.connection.recv(4096)
            if not data:
                logging.info(f"Connection from {self.username} ({self.player_id}) closed by client.")
                break
            
            buffer += data.decode('utf-8')
            while '\n' in buffer:
                message, buffer = buffer.split('\n', 1)
                if message:
                    try:
                        action_data = json.loads(message)
                        logging.info(f"Action from {self.username} ({self.player_id}): {action_data}")
                        self.game.handle_action(self.player_id, action_data)
                        self.broadcast_state()
                    except json.JSONDecodeError:
                        logging.warning(f"Invalid JSON from {self.username}: {message}")

    def _cleanup(self):
        """Removes the client from the game and closes the connection."""
        logging.info(f"Closing connection for {self.username} ({self.player_id})")
        with self.lock:
            removed_player_id = self.clients.pop(self.connection, None)
            if removed_player_id:
                self.game.remove_player(removed_player_id)
        
        self.broadcast_state()
        self.connection.close()

    def broadcast_state(self):
        """Sends the current game state to all connected clients."""
        with self.lock:
            if not self.clients: return
            state = self.game.get_state()
            # Add player usernames to the broadcast state for consistent display
            state['player_usernames'] = self.game.player_usernames
            full_message = {"type": "game_state", "data": state}
            state_json = json.dumps(full_message) + '\n'
            
            for client_conn in list(self.clients.keys()):
                try:
                    client_conn.sendall(state_json.encode('utf-8'))
                except (socket.error, BrokenPipeError):
                    logging.warning(f"Failed to send to a disconnected client. It will be removed.")