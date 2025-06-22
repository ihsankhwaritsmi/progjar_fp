# file: server.py
import socket
import threading
import json
import uuid
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NumberGuessGame:
    # ... (init, _get_current_player_id, _update_round_state, add_player, remove_player tetap sama) ...
    # Salin semua metode yang tidak berubah dari kode sebelumnya.
    def __init__(self, required_players=2):
        self.required_players = required_players
        self.players = {}
        self.current_round = 0
        self.round_state = "WAITING_FOR_PLAYERS"
        self.round_message = f"Waiting for {required_players} players to join..."
        self.actual_total = 0
        self.lock = threading.Lock()
        self.turn_order = []
        self.current_turn_index = 0
        self.player_usernames = {}  # Add this line to store usernames
    def _get_current_player_id(self):
        if not self.turn_order or self.current_turn_index >= len(self.turn_order): return None
        return self.turn_order[self.current_turn_index]
    def _update_round_state(self, new_state, message=""):
        self.round_state = new_state; self.round_message = message; logging.info(f"Game State Updated: {self.round_state} - {self.round_message}")
    def add_player(self, player_id, username=None):
        with self.lock:
            if player_id in self.players:
                return {"status": "error", "message": "Player ID already exists."}
            if len(self.players) >= self.required_players:
                return {"status": "error", "message": "Game is full."}
            
            self.players[player_id] = {'score': 0, 'raised_number': None, 'guess': None}
            self.turn_order.append(player_id)
            if username:
                self.player_usernames[player_id] = username
            
            logging.info(f"Player {player_id} ({username}) joined. Total players: {len(self.players)}/{self.required_players}. Turn order: {self.turn_order}")
            
            if len(self.players) == self.required_players:
                self.start_new_round()
            else:
                remaining = self.required_players - len(self.players)
                self.round_message = f"Welcome {username or player_id}! Waiting for {remaining} more player(s)."
            return {"status": "ok"}
    def remove_player(self, player_id):
        with self.lock:
            if player_id in self.players:
                # Get username before removing player
                username = self.player_usernames.get(player_id, player_id)
                
                was_current_turn = (player_id == self._get_current_player_id())
                del self.players[player_id]
                self.turn_order.remove(player_id)
                
                # Remove from username mapping as well
                if player_id in self.player_usernames:
                    del self.player_usernames[player_id]
                
                logging.info(f"Player {username} (ID: {player_id}) left. Total players: {len(self.players)}")
                
                if self.round_state != "WAITING_FOR_PLAYERS" and len(self.players) < self.required_players:
                    self._update_round_state("WAITING_FOR_PLAYERS", "A player disconnected. Waiting for players.")
                    self.current_round = 0
                    for pid in self.players:
                        self.players[pid]['score'] = 0
                        self.players[pid]['raised_number'] = None
                        self.players[pid]['guess'] = None
                elif was_current_turn:
                    self._check_for_state_transition()
                return True
            return False

    def start_new_round(self):
        self.current_round += 1
        self.actual_total = 0
        for player_id in self.players:
            self.players[player_id]['raised_number'] = None
            self.players[player_id]['guess'] = None

        self.current_turn_index = 0
        current_player_id = self._get_current_player_id()
        current_username = self.player_usernames.get(current_player_id, current_player_id)
        self._update_round_state(
            "WAITING_FOR_NUMBERS",
            f"Round {self.current_round}: Waiting for {current_username} to raise a number."
        )
        logging.info(f"--- Starting Round {self.current_round} ---")

    def handle_action(self, player_id, action_data):
        with self.lock:
            action = action_data.get("action")
            username = self.player_usernames.get(player_id, player_id)  # Get username once at start
            
            if self.round_state == "WAITING_FOR_NUMBERS":
                current_player_id = self._get_current_player_id()
                if player_id != current_player_id: 
                    return  # Only current player can raise
                
                if action == "raise_number":
                    number = action_data.get("number")
                    if number in [1, 2] and self.players[player_id]['raised_number'] is None:
                        self.players[player_id]['raised_number'] = number
                        logging.info(f"Player {username} (ID: {player_id}) raised: {number}")
                        self.current_turn_index += 1
                        self._check_for_state_transition()
            
            elif self.round_state == "WAITING_FOR_GUESSES":
                # Determine designated guesser for this round
                designated_guesser_index = (self.current_round - 1) % len(self.turn_order)
                designated_guesser_id = self.turn_order[designated_guesser_index]
                designated_username = self.player_usernames.get(designated_guesser_id, designated_guesser_id)

                # Only process action from designated guesser
                if player_id != designated_guesser_id:
                    logging.warning(f"Guess from {username} (ID: {player_id}) ignored. It's {designated_username}'s turn to guess this round.")
                    return

                if action == "make_guess":
                    guess = action_data.get("guess")
                    min_guess, max_guess = len(self.players), len(self.players) * 2
                    if not (isinstance(guess, int) and min_guess <= guess <= max_guess): 
                        return

                    self.players[player_id]['guess'] = guess
                    logging.info(f"Player {username} (ID: {player_id}) submitted guess: {guess}")
                    
                    result_message = ""
                    if guess == self.actual_total:
                        self.players[player_id]['score'] += 1
                        result_message = f"Round {self.current_round} Over! {username} guessed correctly ({guess}) and wins!"
                    else:
                        result_message = f"Round {self.current_round} Over! {username} guessed {guess}, but the total was {self.actual_total}."
                    
                    self._update_round_state("ROUND_OVER", result_message)
                    logging.info(result_message)
            
            elif action == "start_new_round" and self.round_state == "ROUND_OVER":
                self.start_new_round()

    def _check_for_state_transition(self):
        if self.round_state == "WAITING_FOR_NUMBERS":
            if self.current_turn_index >= len(self.turn_order):  # All players have raised
                self.actual_total = sum(p['raised_number'] for p in self.players.values())
                designated_guesser_index = (self.current_round - 1) % len(self.turn_order)
                designated_guesser_id = self.turn_order[designated_guesser_index]
                designated_username = self.player_usernames.get(designated_guesser_id, designated_guesser_id)
                self._update_round_state(
                    "WAITING_FOR_GUESSES", 
                    f"All numbers are in! Waiting for {designated_username} to submit a guess."
                )
                logging.info(f"All players raised. Actual total is {self.actual_total} (hidden).")
            else:  # Still waiting for players to raise
                next_player = self._get_current_player_id()
                next_username = self.player_usernames.get(next_player, next_player)
                self._update_round_state(
                    "WAITING_FOR_NUMBERS", 
                    f"Waiting for {next_username} to raise a number."
                )
                
    def get_state(self):
        with self.lock:
            active_player_id = None
            if self.round_state == 'WAITING_FOR_NUMBERS':
                active_player_id = self._get_current_player_id()
            elif self.round_state == 'WAITING_FOR_GUESSES':
                designated_guesser_index = (self.current_round - 1) % len(self.turn_order)
                active_player_id = self.turn_order[designated_guesser_index]
                
            return {
                "current_round": self.current_round,
                "round_state": self.round_state,
                "round_message": self.round_message,
                "players": self.players,
                "actual_total": self.actual_total if self.round_state == "ROUND_OVER" else None,
                "required_players": self.required_players,
                "active_player_id": active_player_id,
                "player_usernames": self.player_usernames  # Add this line
            }
# --- KELAS ProcessTheClient dan Server (TIDAK ADA PERUBAHAN) ---
# ... (Salin-tempel seluruh kelas ProcessTheClient, Server, dan fungsi main dari kode sebelumnya) ...
class ProcessTheClient(threading.Thread):
    def __init__(self, connection, address, game_instance, clients_dict, lock): self.connection = connection; self.address = address; self.game = game_instance; self.clients = clients_dict; self.lock = lock; self.player_id = None; threading.Thread.__init__(self)
    def broadcast_state(self):
        with self.lock:
            if not self.clients: return
            state = self.game.get_state(); full_message = {"type": "game_state", "data": state}; state_json = json.dumps(full_message) + '\n'
            for client_conn in list(self.clients.keys()):
                try: client_conn.sendall(state_json.encode('utf-8'))
                except (socket.error, BrokenPipeError): logging.warning(f"Gagal mengirim ke klien yang terputus.")
    def run(self):
        self.player_id = f"player_{uuid.uuid4().hex[:6]}"
        logging.info(f"Processing connection from {self.address} for {self.player_id}")
        
        # First receive the username from client
        buffer = ""
        username = self.player_id  # Default to player_id if username not received
        try:
            # Wait for initial message containing username
            while '\n' not in buffer:
                data = self.connection.recv(4096)
                if not data:
                    self.connection.close()
                    return
                buffer += data.decode('utf-8')
            
            # Extract username from first message
            message, buffer = buffer.split('\n', 1)
            welcome_data = json.loads(message)
            username = welcome_data.get("username", self.player_id)
            
        except (json.JSONDecodeError, KeyError, socket.error) as e:
            logging.warning(f"Error receiving username from {self.address}: {e}")
            username = self.player_id
        
        # Add player to game with username
        join_result = self.game.add_player(self.player_id, username)
        if join_result.get("status") == "error":
            error_msg = json.dumps({"type": "error", "message": join_result["message"]}) + '\n'
            self.connection.sendall(error_msg.encode('utf-8'))
            self.connection.close()
            return
        
        # Store connection in clients dict
        with self.lock:
            self.clients[self.connection] = self.player_id
        
        # Send welcome message with assigned player_id
        welcome_msg = json.dumps({
            "type": "welcome",
            "player_id": self.player_id,
            "username": username
        }) + '\n'
        self.connection.sendall(welcome_msg.encode('utf-8'))
        
        # Broadcast initial game state
        self.broadcast_state()
        
        # Main message processing loop
        try:
            while True:
                # Receive data from client
                data = self.connection.recv(4096)
                if not data:
                    logging.info(f"Connection from {username} ({self.player_id}) closed by client.")
                    break
                
                buffer += data.decode('utf-8')
                
                # Process complete messages (delimited by newline)
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    if message:
                        try:
                            action_data = json.loads(message)
                            logging.info(f"Action from {username} ({self.player_id}): {action_data}")
                            self.game.handle_action(self.player_id, action_data)
                            self.broadcast_state()
                        except json.JSONDecodeError:
                            logging.warning(f"Invalid JSON from {username} ({self.player_id}): {message}")
        
        except (socket.error, ConnectionResetError) as e:
            logging.warning(f"Connection with {username} ({self.player_id}) lost: {e}")
        
        finally:
            logging.info(f"Closing connection for {username} ({self.player_id}) from {self.address}")
            with self.lock:
                removed_player_id = self.clients.pop(self.connection, None)
                if removed_player_id:
                    self.game.remove_player(removed_player_id)
            
            # Broadcast updated state after player leaves
            self.broadcast_state()
            self.connection.close()

class Server(threading.Thread):
    def __init__(self, port=8000): self.game = NumberGuessGame(required_players=2); self.clients = {}; self.lock = threading.Lock(); self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM); self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); self.port = port; threading.Thread.__init__(self)
    def run(self):
        self.my_socket.bind(('0.0.0.0', self.port)); self.my_socket.listen(5); logging.info(f"Server utama mendengarkan di port {self.port}")
        try:
            while True: connection, client_address = self.my_socket.accept(); logging.info(f"Koneksi baru diterima dari {client_address}"); clt = ProcessTheClient(connection, client_address, self.game, self.clients, self.lock); clt.start()
        except KeyboardInterrupt: logging.info("\nServer dimatikan.")
        finally: self.my_socket.close()

import time

def main():
    server_port = 8000
    svr = Server(port=server_port)
    svr.daemon = True
    svr.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer dimatikan oleh user.")

if __name__ == "__main__":
    main()