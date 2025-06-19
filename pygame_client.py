import pygame
import socket
import threading
import json
import sys

# Konfigurasi Warna dan Font
COLOR_BG = (240, 240, 240)
COLOR_TEXT = (10, 10, 10)
COLOR_PLAYER_ME = (0, 100, 200)
COLOR_DISABLED = (170, 170, 170)
COLOR_BUTTON = (0, 150, 136)
COLOR_BUTTON_HOVER = (0, 170, 156)
COLOR_INPUT_ACTIVE = (0, 100, 200)
COLOR_INPUT_INACTIVE = (100, 100, 100)

class PygameClientApp:
    def __init__(self):
        # Pengaturan Jaringan
        self.server_host = "localhost"
        self.server_port = 8000
        self.client_socket = None
        self.running = True
        
        # State Game
        self.player_id = None
        self.game_state = {}
        self.status_message = "Connecting to server..."
        
        # Pengaturan Pygame
        pygame.init()
        self.screen_width = 700
        self.screen_height = 550
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Number Guess Game")
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 28)

        # Elemen UI (Rectangles untuk deteksi klik) - # DIUBAH: Tata letak Y diperbaiki
        y_start_actions = 250 # Posisi Y awal untuk semua tombol aksi
        button_width = 200
        button_height = 50
        padding = 15

        # Baris 1: Tombol Raise
        self.btn_raise_1_rect = pygame.Rect(self.screen_width/2 - button_width - padding/2, y_start_actions, button_width, button_height)
        self.btn_raise_2_rect = pygame.Rect(self.screen_width/2 + padding/2, y_start_actions, button_width, button_height)
        
        # Baris 2: Input dan Tombol Guess
        y_row_2 = y_start_actions + button_height + padding
        self.input_box_rect = pygame.Rect(self.screen_width/2 - button_width - padding/2, y_row_2, button_width, button_height)
        self.btn_guess_rect = pygame.Rect(self.screen_width/2 + padding/2, y_row_2, button_width, button_height)

        # Tombol Start New Round (akan diposisikan di tengah)
        self.btn_start_new_rect = pygame.Rect(self.screen_width/2 - button_width/2, y_row_2, button_width, button_height)
        
        # State Input
        self.input_text = ""
        self.input_active = False

        # Memulai thread jaringan
        self.network_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.network_thread.start()

    # ... (network_loop, handle_server_message, send_action tidak berubah) ...
    # Salin semua fungsi dari versi sebelumnya yang tidak diubah di sini
    def network_loop(self):
        """Menghubungkan ke server dan mendengarkan pesan (TIDAK BERUBAH dari versi Tkinter)."""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_host, self.server_port))
        except (socket.error, ConnectionRefusedError) as e:
            self.status_message = "Connection failed. Is the server running?"
            print(f"Connection error: {e}")
            self.running = False
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
        
        self.status_message = "Disconnected from server."
        print("Disconnected from server.")
        self.running = False

    def handle_server_message(self, message_str):
        """Mem-parsing pesan dari server dan update state (hampir sama, tanpa `master.after`)."""
        try:
            message = json.loads(message_str)
            msg_type = message.get("type")

            if msg_type == "welcome":
                self.player_id = message.get("player_id")
                pygame.display.set_caption(f"Number Guess Game - {self.player_id}")
            
            elif msg_type == "game_state":
                self.game_state = message.get("data", {})
            
            elif msg_type == "error":
                self.status_message = f"Server Error: {message.get('message')}"
                print(f"Server Error: {message.get('message')}")
                self.running = False # Tutup klien jika ada error fatal

        except json.JSONDecodeError:
            print(f"Received invalid JSON: {message_str}")

    def send_action(self, action_type, data={}):
        """Mengirim aksi JSON ke server (TIDAK BERUBAH)."""
        if not self.client_socket or not self.running:
            return
        payload = {"action": action_type, **data}
        try:
            message = json.dumps(payload) + '\n'
            self.client_socket.sendall(message.encode('utf-8'))
        except socket.error as e:
            print(f"Failed to send action: {e}")

    def submit_guess(self):
        """Mengirim tebakan dari kotak input."""
        if self.input_text:
            try:
                guess = int(self.input_text)
                self.send_action("make_guess", {"guess": guess})
                self.input_text = ""
            except ValueError:
                print("Invalid number entered.")
                self.input_text = ""

    def draw_text(self, text, font, color, x, y, center=False):
        """Helper function untuk menggambar teks."""
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        if center:
            text_rect.center = (x, y)
        else:
            text_rect.topleft = (x, y)
        self.screen.blit(text_surface, text_rect)

    def draw_button(self, rect, text, enabled=True):
        """Helper function untuk menggambar tombol."""
        mouse_pos = pygame.mouse.get_pos()
        is_hovering = rect.collidepoint(mouse_pos)
        
        btn_color = COLOR_BUTTON if enabled else COLOR_DISABLED
        if is_hovering and enabled:
            btn_color = COLOR_BUTTON_HOVER
        
        pygame.draw.rect(self.screen, btn_color, rect, border_radius=8)
        self.draw_text(text, self.font_medium, COLOR_BG, rect.centerx, rect.centery, center=True)

    def draw_scene(self):
        """Menggambar seluruh tampilan game berdasarkan game_state."""
        self.screen.fill(COLOR_BG)
        state = self.game_state

        if not state:
            self.draw_text(self.status_message, self.font_big, COLOR_TEXT, self.screen_width // 2, self.screen_height // 2, center=True)
            return

        # Gambar status utama dan pesan ronde
        self.draw_text(f"Game State: {state.get('round_state', 'N/A')}", self.font_big, COLOR_TEXT, self.screen_width // 2, 30, center=True)
        self.draw_text(state.get('round_message', ''), self.font_medium, COLOR_TEXT, self.screen_width // 2, 80, center=True)

        # Gambar info pemain
        y_pos = 140
        my_player_data = state.get('players', {}).get(self.player_id, {})
        for pid, pdata in state.get('players', {}).items():
            is_me = (pid == self.player_id)
            player_text = f"{pid} (You)" if is_me else pid
            player_info = f"{player_text} | Score: {pdata['score']}"
            
            # ... logika info pemain tidak berubah
            if state['round_state'] == 'WAITING_FOR_NUMBERS':
                status = "Raised: Yes" if pdata.get('raised_number') is not None else "Raised: No"
                player_info += f" | {status}"
            elif state['round_state'] == 'WAITING_FOR_GUESSES':
                guessed = 'Yes' if pdata.get('guess') is not None else 'No'
                player_info += f" | Guessed: {guessed}"
            elif state['round_state'] == 'ROUND_OVER':
                raised = pdata.get('raised_number', '?')
                guess = pdata.get('guess', '?')
                player_info += f" | Raised: {raised} | Guessed: {guess}"
            
            self.draw_text(player_info, self.font_medium, COLOR_PLAYER_ME if is_me else COLOR_TEXT, 50, y_pos)
            y_pos += 35

        # Tentukan apakah tombol/input aktif
        can_raise = (state.get('round_state') == "WAITING_FOR_NUMBERS" and my_player_data.get('raised_number') is None)
        can_guess = (state.get('round_state') == "WAITING_FOR_GUESSES" and my_player_data.get('guess') is None)
        can_start_new = (state.get('round_state') == "ROUND_OVER")

        # DIUBAH: Logika penggambaran dipisah berdasarkan state
        if can_start_new:
            # HANYA gambar tombol "Start Next Round" jika game over
            self.draw_button(self.btn_start_new_rect, "Start Next Round", enabled=True)
        else:
            # Gambar elemen untuk ronde yang sedang berjalan
            # 1. Tombol Raise
            self.draw_button(self.btn_raise_1_rect, "Raise 1", enabled=can_raise)
            self.draw_button(self.btn_raise_2_rect, "Raise 2", enabled=can_raise)

            # 2. Input dan Tombol Guess
            self.draw_button(self.btn_guess_rect, "Submit Guess", enabled=can_guess)
            
            # 3. Kotak Input
            input_border_color = COLOR_INPUT_ACTIVE if self.input_active and can_guess else COLOR_INPUT_INACTIVE
            pygame.draw.rect(self.screen, input_border_color, self.input_box_rect, 2, border_radius=5)
            self.draw_text(self.input_text, self.font_medium, COLOR_TEXT, self.input_box_rect.x + 10, self.input_box_rect.y + 12)

    # ... (handle_events dan run tidak berubah) ...
    # Salin semua fungsi dari versi sebelumnya yang tidak diubah di sini
    def handle_events(self):
        """Menangani semua input dari user (mouse, keyboard)."""
        state = self.game_state
        if not state: return

        my_player_data = state.get('players', {}).get(self.player_id, {})
        can_raise = (state.get('round_state') == "WAITING_FOR_NUMBERS" and my_player_data.get('raised_number') is None)
        can_guess = (state.get('round_state') == "WAITING_FOR_GUESSES" and my_player_data.get('guess') is None)
        can_start_new = (state.get('round_state') == "ROUND_OVER")

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.MOUSEBUTTONDOWN:
                # DIUBAH: Logika klik disesuaikan dengan state
                if can_start_new:
                    if self.btn_start_new_rect.collidepoint(event.pos):
                        self.send_action("start_new_round")
                else:
                    if self.btn_raise_1_rect.collidepoint(event.pos) and can_raise:
                        self.send_action("raise_number", {"number": 1})
                    elif self.btn_raise_2_rect.collidepoint(event.pos) and can_raise:
                        self.send_action("raise_number", {"number": 2})
                    elif self.btn_guess_rect.collidepoint(event.pos) and can_guess:
                        self.submit_guess()
                    
                    if self.input_box_rect.collidepoint(event.pos) and can_guess:
                        self.input_active = True
                    else:
                        self.input_active = False

            if event.type == pygame.KEYDOWN:
                if self.input_active and can_guess:
                    if event.key == pygame.K_RETURN:
                        self.submit_guess()
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    elif event.unicode.isdigit():
                        self.input_text += event.unicode
    
    def run(self):
        """Game loop utama."""
        while self.running:
            self.handle_events()
            self.draw_scene()
            pygame.display.flip()
            self.clock.tick(30) # Batasi FPS
        
        # Cleanup
        if self.client_socket:
            self.client_socket.close()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = PygameClientApp()
    app.run()