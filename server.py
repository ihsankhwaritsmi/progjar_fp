import socket
import threading
import json
import uuid
import logging

# --- Konfigurasi Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Game Logic Class (TIDAK BERUBAH) ---
# Kelas ini sudah bagus dan tidak perlu diubah.
# Ia mengelola state game secara independen dari cara kita berkomunikasi.
class NumberGuessGame:
    """Manages the state and logic of the number guessing game."""
    def __init__(self, required_players=2):
        self.required_players = required_players
        self.players = {}
        self.current_round = 0
        self.round_state = "WAITING_FOR_PLAYERS"
        self.round_message = f"Waiting for {required_players} players to join..."
        self.actual_total = 0
        self.lock = threading.Lock()

    def _update_round_state(self, new_state, message=""):
        self.round_state = new_state
        self.round_message = message
        logging.info(f"Game State Updated: {self.round_state} - {self.round_message}")

    def add_player(self, player_id):
        with self.lock:
            if player_id in self.players:
                return {"status": "error", "message": "Player ID already exists."}
            if len(self.players) >= self.required_players:
                return {"status": "error", "message": "Game is full."}
            self.players[player_id] = {'score': 0, 'raised_number': None, 'guess': None}
            logging.info(f"Player {player_id} joined. Total players: {len(self.players)}/{self.required_players}")
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
                logging.info(f"Player {player_id} left. Total players: {len(self.players)}")
                if self.round_state != "WAITING_FOR_PLAYERS" and len(self.players) < self.required_players:
                    self._update_round_state("WAITING_FOR_PLAYERS", f"A player disconnected. Waiting for players to start.")
                    self.current_round = 0
                    for pid in self.players:
                        self.players[pid]['score'] = 0
                        self.players[pid]['raised_number'] = None
                        self.players[pid]['guess'] = None
                return True
            return False

    def start_new_round(self):
        self.current_round += 1
        self._update_round_state("WAITING_FOR_NUMBERS", f"Round {self.current_round}: All players, raise 1 or 2!")
        self.actual_total = 0
        for player_id in self.players:
            self.players[player_id]['raised_number'] = None
            self.players[player_id]['guess'] = None
        logging.info(f"--- Starting Round {self.current_round} ---")

    def handle_action(self, player_id, action_data):
        with self.lock:
            action = action_data.get("action")
            if action == "raise_number" and self.round_state == "WAITING_FOR_NUMBERS":
                number = action_data.get("number")
                if number in [1, 2] and self.players[player_id]['raised_number'] is None:
                    self.players[player_id]['raised_number'] = number
                    logging.info(f"Player {player_id} raised: {number}")
            elif action == "make_guess" and self.round_state == "WAITING_FOR_GUESSES":
                guess = action_data.get("guess")
                min_guess, max_guess = len(self.players), len(self.players) * 2
                if isinstance(guess, int) and min_guess <= guess <= max_guess and self.players[player_id]['guess'] is None:
                    self.players[player_id]['guess'] = guess
                    logging.info(f"Player {player_id} guessed: {guess}")
            elif action == "start_new_round" and self.round_state == "ROUND_OVER":
                self.start_new_round()
            self._check_for_state_transition()

    def _check_for_state_transition(self):
        if self.round_state == "WAITING_FOR_NUMBERS" and len(self.players) == self.required_players:
            if all(p['raised_number'] is not None for p in self.players.values()):
                self.actual_total = sum(p['raised_number'] for p in self.players.values())
                self._update_round_state("WAITING_FOR_GUESSES", "All numbers are in! Now, guess the total.")
                logging.info(f"All players raised numbers. Actual total is {self.actual_total} (hidden).")
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
        logging.info(result_message)

    def get_state(self):
        with self.lock:
            return {
                "current_round": self.current_round, "round_state": self.round_state,
                "round_message": self.round_message, "players": self.players,
                "actual_total": self.actual_total if self.round_state == "ROUND_OVER" else None,
                "required_players": self.required_players,
            }

# --- KELAS UNTUK MEMPROSES KLIEN (SESUAI ARSITEKTUR BARU) ---
class ProcessTheClient(threading.Thread):
    def __init__(self, connection, address, game_instance, clients_dict, lock):
        self.connection = connection
        self.address = address
        # Objek-objek ini dibagikan oleh semua thread
        self.game = game_instance
        self.clients = clients_dict
        self.lock = lock
        self.player_id = None
        threading.Thread.__init__(self)

    def broadcast_state(self):
        """Mengirim game state terbaru ke SEMUA klien yang terhubung."""
        with self.lock:
            if not self.clients:
                return
            state = self.game.get_state()
            full_message = {"type": "game_state", "data": state}
            # Kita menggunakan \n sebagai pemisah pesan, bukan \r\n
            state_json = json.dumps(full_message) + '\n'
            
            for client_conn in list(self.clients.keys()):
                try:
                    client_conn.sendall(state_json.encode('utf-8'))
                except (socket.error, BrokenPipeError):
                    logging.warning(f"Gagal mengirim ke klien yang terputus. Menghapus klien.")
                    # Kita tidak hapus di sini, biarkan loop utama yang menghapus
                    # agar tidak terjadi deadlock
                    pass

    def run(self):
        self.player_id = f"player_{uuid.uuid4().hex[:6]}"
        logging.info(f"Memproses koneksi dari {self.address} untuk {self.player_id}")

        join_result = self.game.add_player(self.player_id)
        if join_result.get("status") == "error":
            error_msg = json.dumps({"type": "error", "message": join_result["message"]}) + '\n'
            self.connection.sendall(error_msg.encode('utf-8'))
            self.connection.close()
            return
        
        # Jika berhasil bergabung, tambahkan ke daftar klien aktif
        with self.lock:
            self.clients[self.connection] = self.player_id
            
        # Kirim pesan selamat datang
        welcome_msg = json.dumps({"type": "welcome", "player_id": self.player_id}) + '\n'
        self.connection.sendall(welcome_msg.encode('utf-8'))

        # Siarkan state game awal ke semua pemain
        self.broadcast_state()

        buffer = ""
        try:
            while True:
                data = self.connection.recv(4096)
                if not data:
                    logging.info(f"Koneksi dari {self.player_id} ditutup oleh klien.")
                    break
                
                buffer += data.decode('utf-8')
                # Proses semua pesan lengkap di dalam buffer (dipisahkan oleh \n)
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    if message:
                        try:
                            action_data = json.loads(message)
                            logging.info(f"Data dari {self.player_id}: {action_data}")
                            self.game.handle_action(self.player_id, action_data)
                            self.broadcast_state()
                        except json.JSONDecodeError:
                            logging.warning(f"Menerima JSON tidak valid dari {self.player_id}: {message}")
        except (socket.error, ConnectionResetError) as e:
            logging.warning(f"Koneksi dengan {self.player_id} terputus: {e}")
        finally:
            logging.info(f"Menutup koneksi untuk {self.player_id} dari {self.address}")
            # Hapus klien dari daftar dan game state
            with self.lock:
                # Hapus dari dictionary klien
                removed_player_id = self.clients.pop(self.connection, None)
                # Jika pemain memang ada di game, hapus dari logika game
                if removed_player_id:
                    self.game.remove_player(removed_player_id)
            
            # Siarkan state terakhir setelah pemain keluar
            self.broadcast_state()
            self.connection.close()

# --- KELAS SERVER UTAMA (SESUAI ARSITEKTUR BARU) ---
class Server(threading.Thread):
    def __init__(self, port=8000):
        # State yang akan dibagikan ke semua thread klien
        self.game = NumberGuessGame(required_players=2)
        self.clients = {}  # {connection: player_id}
        self.lock = threading.Lock() # Lock untuk melindungi akses ke self.clients

        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.port = port
        threading.Thread.__init__(self)

    def run(self):
        self.my_socket.bind(('0.0.0.0', self.port))
        self.my_socket.listen(5)
        logging.info(f"Server utama mendengarkan di port {self.port}")

        try:
            while True:
                connection, client_address = self.my_socket.accept()
                logging.info(f"Koneksi baru diterima dari {client_address}")

                # Buat thread baru untuk memproses klien ini
                # Berikan akses ke game state, daftar klien, dan lock
                clt = ProcessTheClient(connection, client_address, self.game, self.clients, self.lock)
                clt.start()
        except KeyboardInterrupt:
            logging.info("\nServer dimatikan.")
        finally:
            self.my_socket.close()

def main():
    # Ganti port di sini jika perlu
    server_port = 8000
    svr = Server(port=server_port)
    svr.start()

if __name__ == "__main__":
    main()