import socket
import threading
import json
import uuid

# --- Game Logic Class (Copied from previous version, no changes needed) ---
class NumberGuessGame:
    """
    Manages the state and logic of the number guessing game.
    This class is independent of the network protocol used.
    """
    def __init__(self, required_players=2):
        self.required_players = required_players
        self.players = {}  # {'player_id': {'score': 0, 'raised_number': None, 'guess': None}}
        self.current_round = 0
        # Possible States: WAITING_FOR_PLAYERS, WAITING_FOR_NUMBERS, WAITING_FOR_GUESSES, ROUND_OVER
        self.round_state = "WAITING_FOR_PLAYERS"
        self.round_message = f"Waiting for {required_players} players to join..."
        self.actual_total = 0
        self.lock = threading.Lock() # Protects shared game state from concurrent access

    def _update_round_state(self, new_state, message=""):
        self.round_state = new_state
        self.round_message = message
        print(f"Game State Updated: {self.round_state} - {self.round_message}")

    def add_player(self, player_id):
        with self.lock:
            if player_id in self.players:
                return {"status": "error", "message": "Player ID already exists."}
            
            if len(self.players) >= self.required_players:
                 return {"status": "error", "message": "Game is full."}

            self.players[player_id] = {'score': 0, 'raised_number': None, 'guess': None}
            print(f"Player {player_id} joined. Total players: {len(self.players)}/{self.required_players}")
            
            if len(self.players) == self.required_players:
                self.start_new_round()
            else:
                remaining = self.required_players - len(self.players)
                self.round_message = f"Welcome {player_id}! Waiting for {remaining} more player(s)."
            
            return {"status": "ok"}

    def remove_player(self, player_id):
        with self.lock:
            if player_id in self.players:
                del self.players[player_id]
                print(f"Player {player_id} left. Total players: {len(self.players)}")
                # Reset game if a player leaves mid-game and the game was running
                if self.round_state != "WAITING_FOR_PLAYERS" and len(self.players) < self.required_players:
                    self._update_round_state("WAITING_FOR_PLAYERS", f"A player disconnected. Waiting for players to start.")
                    self.current_round = 0
                    # Reset remaining players' scores and states
                    for pid in self.players:
                        self.players[pid]['score'] = 0
                        self.players[pid]['raised_number'] = None
                        self.players[pid]['guess'] = None
                return True
            return False

    def start_new_round(self):
        # This is called from within locked methods
        self.current_round += 1
        self._update_round_state("WAITING_FOR_NUMBERS", f"Round {self.current_round}: All players, raise 1 or 2!")
        self.actual_total = 0
        for player_id in self.players:
            self.players[player_id]['raised_number'] = None
            self.players[player_id]['guess'] = None
        print(f"\n--- Starting Round {self.current_round} ---")

    def handle_action(self, player_id, action_data):
        with self.lock:
            action = action_data.get("action")
            if action == "raise_number" and self.round_state == "WAITING_FOR_NUMBERS":
                number = action_data.get("number")
                if number in [1, 2] and self.players[player_id]['raised_number'] is None:
                    self.players[player_id]['raised_number'] = number
                    print(f"Player {player_id} raised: {number}")
            
            elif action == "make_guess" and self.round_state == "WAITING_FOR_GUESSES":
                guess = action_data.get("guess")
                min_guess, max_guess = len(self.players), len(self.players) * 2
                if isinstance(guess, int) and min_guess <= guess <= max_guess and self.players[player_id]['guess'] is None:
                    self.players[player_id]['guess'] = guess
                    print(f"Player {player_id} guessed: {guess}")

            elif action == "start_new_round" and self.round_state == "ROUND_OVER":
                 self.start_new_round()

            # Check for state transitions after every action
            self._check_for_state_transition()

    def _check_for_state_transition(self):
        # This method assumes it's called from within a locked context
        if self.round_state == "WAITING_FOR_NUMBERS" and len(self.players) == self.required_players:
            if all(p['raised_number'] is not None for p in self.players.values()):
                self.actual_total = sum(p['raised_number'] for p in self.players.values())
                self._update_round_state("WAITING_FOR_GUESSES", "All numbers are in! Now, guess the total.")
                print(f"All players raised numbers. Actual total is {self.actual_total} (hidden from players).")
        
        elif self.round_state == "WAITING_FOR_GUESSES" and len(self.players) == self.required_players:
            if all(p['guess'] is not None for p in self.players.values()):
                self._calculate_round_results()

    def _calculate_round_results(self):
        winners = [pid for pid, pdata in self.players.items() if pdata['guess'] == self.actual_total]
        for winner_id in winners:
            self.players[winner_id]['score'] += 1

        if winners:
            winner_names = ", ".join(winners)
            result_message = f"Round {self.current_round} Over! Total was {self.actual_total}. Winner(s): {winner_names}!"
        else:
            result_message = f"Round {self.current_round} Over! Total was {self.actual_total}. No winners."
        
        self._update_round_state("ROUND_OVER", result_message)
        print(result_message)

    def get_state(self):
        with self.lock:
            # Create a copy to be sent to clients
            return {
                "current_round": self.current_round,
                "round_state": self.round_state,
                "round_message": self.round_message,
                "players": self.players,
                "actual_total": self.actual_total if self.round_state == "ROUND_OVER" else None,
                "required_players": self.required_players,
            }

# --- Socket Server ---
class GameServer:
    def __init__(self, host='0.0.0.0', port=8000):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.game = NumberGuessGame(required_players=2)
        self.clients = {}  # {conn: player_id}
        self.lock = threading.Lock()

    def broadcast_state(self):
        """Sends the current game state to all connected clients."""
        with self.lock:
            if not self.clients:
                return
            
            state = self.game.get_state()
            # Add message type for client-side handling
            full_message = {"type": "game_state", "data": state}
            state_json = json.dumps(full_message) + '\n' # Use newline as a message delimiter
            
            for client_conn in list(self.clients.keys()):
                try:
                    client_conn.sendall(state_json.encode('utf-8'))
                except (socket.error, BrokenPipeError):
                    print(f"Failed to send to a client. Removing.")
                    self._remove_client(client_conn)

    def _remove_client(self, conn):
        """Removes a client from the game and connection list."""
        player_id = self.clients.pop(conn, None)
        if player_id:
            self.game.remove_player(player_id)
        try:
            conn.close()
        except socket.error:
            pass # Ignore errors on close
        # After removing, broadcast the new state
        self.broadcast_state()

    def handle_client(self, conn, addr):
        """Manages a single client's connection and messages in a thread."""
        print(f"New connection from {addr}")
        player_id = f"player_{uuid.uuid4().hex[:6]}"
        
        # Add player and register client connection
        join_result = self.game.add_player(player_id)
        
        if join_result.get("status") == "error":
            error_msg = json.dumps({"type": "error", "message": join_result["message"]}) + '\n'
            conn.sendall(error_msg.encode('utf-8'))
            conn.close()
            return

        with self.lock:
            self.clients[conn] = player_id
            
        # Send a welcome message with the assigned player_id
        welcome_msg = json.dumps({"type": "welcome", "player_id": player_id}) + '\n'
        conn.sendall(welcome_msg.encode('utf-8'))

        # Initial state broadcast
        self.broadcast_state()

        buffer = ""
        try:
            while True:
                data = conn.recv(4096).decode('utf-8')
                if not data:
                    break # Client disconnected
                
                buffer += data
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    try:
                        action_data = json.loads(message)
                        self.game.handle_action(player_id, action_data)
                        self.broadcast_state()
                    except json.JSONDecodeError:
                        print(f"Received invalid JSON from {player_id}: {message}")

        except (socket.error, ConnectionResetError):
            print(f"Connection with {player_id} lost.")
        finally:
            print(f"Closing connection for {player_id} from {addr}")
            with self.lock:
                self._remove_client(conn)

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Server listening on {self.host}:{self.port}")
        
        try:
            while True:
                conn, addr = self.server_socket.accept()
                thread = threading.Thread(target=self.handle_client, args=(conn, addr))
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            print("\nShutting down server.")
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    server = GameServer()
    server.start()
