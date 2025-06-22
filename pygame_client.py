import pygame
import socket
import threading
import json
import sys
import math

# Enhanced Color Scheme - Modern Dark Theme
COLOR_BG = (32, 35, 40)  # Dark background
COLOR_SURFACE = (45, 50, 57)  # Card/surface color
COLOR_PRIMARY = (100, 181, 246)  # Light blue primary
COLOR_PRIMARY_HOVER = (129, 199, 255)  # Lighter blue for hover
COLOR_SECONDARY = (76, 175, 80)  # Green secondary
COLOR_SECONDARY_HOVER = (102, 187, 106)  # Lighter green
COLOR_ACCENT = (255, 193, 7)  # Golden accent
COLOR_TEXT = (255, 255, 255)  # White text
COLOR_TEXT_SECONDARY = (158, 158, 158)  # Gray text
COLOR_ERROR = (244, 67, 54)  # Red for errors
COLOR_SUCCESS = (76, 175, 80)  # Green for success
COLOR_INPUT_BG = (55, 61, 69)  # Input background
COLOR_INPUT_BORDER = (100, 181, 246)  # Input border when active
COLOR_INPUT_BORDER_INACTIVE = (97, 97, 97)  # Input border when inactive
COLOR_SHADOW = (20, 22, 25)  # Shadow color

class PygameClientApp:
    def __init__(self):
        # Game States
        self.STATE_USERNAME = "username_input"
        self.STATE_CONNECTING = "connecting"
        self.STATE_GAME = "game"
        
        # Current state
        self.current_state = self.STATE_USERNAME
        
        # Username input
        self.username = ""
        self.username_input_active = True
        self.username_error = ""
        
        # Network settings
        self.server_host = "localhost"
        self.server_port = 8000
        self.client_socket = None
        self.running = True
        
        # Game state
        self.player_id = None
        self.game_state = {}
        self.status_message = ""
        self.player_usernames = {}  # Store player ID to username mapping
        
        # Pygame setup
        pygame.init()
        self.screen_width = 900
        self.screen_height = 700
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Number Guess Game")
        self.clock = pygame.time.Clock()
        
        # Enhanced fonts
        self.font_title = pygame.font.Font(None, 56)
        self.font_big = pygame.font.Font(None, 42)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 24)
        
        # Animation variables
        self.animation_time = 0

        # Load images for animation
        self.thumb_image = pygame.image.load("Thumb.png").convert_alpha()
        self.twothumbs_image = pygame.image.load("twoThumbs.png").convert_alpha()

        # Resize images (optional)
        self.thumb_image = pygame.transform.scale(self.thumb_image, (800, 800))
        self.twothumbs_image = pygame.transform.scale(self.twothumbs_image, (800, 800))

        # Animation control
        self.raise_animation = {
            "active": False,
            "image": None,
            "start_time": 0,
            "duration": 1500  # in milliseconds
        }

        # UI Elements setup
        self.setup_ui_elements()

        
    def setup_ui_elements(self):
        """Setup all UI element positions and sizes"""
        # Username input page elements
        self.username_input_rect = pygame.Rect(self.screen_width//2 - 200, self.screen_height//2 - 20, 400, 60)
        self.username_connect_btn = pygame.Rect(self.screen_width//2 - 100, self.screen_height//2 + 80, 200, 50)
        
        # Game UI elements
        button_width = 180
        button_height = 50
        padding = 20
        
        # Center the button layout
        total_width = (button_width * 2) + padding
        start_x = (self.screen_width - total_width) // 2
        
        y_start_actions = 480
        
        # Row 1: Raise buttons
        self.btn_raise_1_rect = pygame.Rect(start_x, y_start_actions, button_width, button_height)
        self.btn_raise_2_rect = pygame.Rect(start_x + button_width + padding, y_start_actions, button_width, button_height)
        
        # Row 2: Input and Guess button
        y_row_2 = y_start_actions + button_height + padding
        self.input_box_rect = pygame.Rect(start_x, y_row_2, button_width, button_height)
        self.btn_guess_rect = pygame.Rect(start_x + button_width + padding, y_row_2, button_width, button_height)
        
        # Start new round button (centered)
        self.btn_start_new_rect = pygame.Rect(self.screen_width//2 - button_width//2, y_row_2, button_width, button_height)
        
        # Game input state
        self.input_text = ""
        self.input_active = False

    def connect_to_server(self):
        """Connect to server with username"""
        self.current_state = self.STATE_CONNECTING
        self.status_message = "Connecting to server..."
        
        # Start network thread
        self.network_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.network_thread.start()

    def network_loop(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_host, self.server_port))
            
            # Send username immediately after connection
            welcome_message = {"username": self.username}
            message = json.dumps(welcome_message) + '\n'
            self.client_socket.sendall(message.encode('utf-8'))
            
        except (socket.error, ConnectionRefusedError) as e:
            self.status_message = "Connection failed. Is the server running?"
            self.username_error = "Connection failed. Please try again."
            self.current_state = self.STATE_USERNAME
            print(f"Connection error: {e}")
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
        try:
            message = json.loads(message_str)
            msg_type = message.get("type")
            
            if msg_type == "welcome":
                self.player_id = message.get("player_id")
                self.current_state = self.STATE_GAME
                pygame.display.set_caption(f"Number Guess Game - {self.username}")
                # Store our own username mapping
                self.player_usernames[self.player_id] = self.username
            elif msg_type == "game_state":
                self.game_state = message.get("data", {})
                # Update username mappings if server provides them
                if "player_usernames" in message:
                    self.player_usernames.update(message["player_usernames"])
            elif msg_type == "error":
                error_msg = message.get('message', 'Unknown error')
                if self.current_state == self.STATE_CONNECTING:
                    self.username_error = error_msg
                    self.current_state = self.STATE_USERNAME
                else:
                    self.status_message = f"Server Error: {error_msg}"
                print(f"Server Error: {error_msg}")
                
        except json.JSONDecodeError:
            print(f"Received invalid JSON: {message_str}")

    def send_action(self, action_type, data={}):
        if not self.client_socket or not self.running:
            return
        payload = {"action": action_type, **data}
        try:
            message = json.dumps(payload) + '\n'
            self.client_socket.sendall(message.encode('utf-8'))
        except socket.error as e:
            print(f"Failed to send action: {e}")

    def submit_guess(self):
        if self.input_text:
            try:
                guess = int(self.input_text)
                self.send_action("make_guess", {"guess": guess})
                self.input_text = ""
            except ValueError:
                print("Invalid number entered.")
                self.input_text = ""

    def draw_gradient_rect(self, rect, color1, color2, vertical=True):
        """Draw a gradient rectangle"""
        if vertical:
            for y in range(rect.height):
                ratio = y / rect.height
                r = int(color1[0] + (color2[0] - color1[0]) * ratio)
                g = int(color1[1] + (color2[1] - color1[1]) * ratio)
                b = int(color1[2] + (color2[2] - color1[2]) * ratio)
                pygame.draw.line(self.screen, (r, g, b), 
                               (rect.x, rect.y + y), (rect.x + rect.width, rect.y + y))

    def draw_shadow_rect(self, rect, color, shadow_offset=3):
        """Draw a rectangle with shadow"""
        shadow_rect = rect.copy()
        shadow_rect.x += shadow_offset
        shadow_rect.y += shadow_offset
        pygame.draw.rect(self.screen, COLOR_SHADOW, shadow_rect, border_radius=12)
        pygame.draw.rect(self.screen, color, rect, border_radius=12)

    def draw_text(self, text, font, color, x, y, center=False):
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        if center:
            text_rect.center = (x, y)
        else:
            text_rect.topleft = (x, y)
        self.screen.blit(text_surface, text_rect)
        return text_rect

    def draw_button(self, rect, text, enabled=True, style="primary"):
        """Draw an enhanced button with hover effects and shadows"""
        mouse_pos = pygame.mouse.get_pos()
        is_hovering = rect.collidepoint(mouse_pos)
        
        # Choose colors based on style and state
        if style == "primary":
            btn_color = COLOR_PRIMARY if enabled else COLOR_TEXT_SECONDARY
            hover_color = COLOR_PRIMARY_HOVER
        elif style == "secondary":
            btn_color = COLOR_SECONDARY if enabled else COLOR_TEXT_SECONDARY
            hover_color = COLOR_SECONDARY_HOVER
        else:
            btn_color = COLOR_ACCENT if enabled else COLOR_TEXT_SECONDARY
            hover_color = COLOR_ACCENT
            
        if is_hovering and enabled:
            btn_color = hover_color
            
        # Draw shadow
        if enabled:
            shadow_rect = rect.copy()
            shadow_rect.x += 2
            shadow_rect.y += 2
            pygame.draw.rect(self.screen, COLOR_SHADOW, shadow_rect, border_radius=8)
        
        # Draw button
        pygame.draw.rect(self.screen, btn_color, rect, border_radius=8)
        
        # Draw text
        text_color = COLOR_TEXT if enabled else COLOR_TEXT_SECONDARY
        self.draw_text(text, self.font_medium, text_color, rect.centerx, rect.centery, center=True)

    def draw_input_field(self, rect, text, active, placeholder=""):
        """Draw an enhanced input field"""
        # Background
        pygame.draw.rect(self.screen, COLOR_INPUT_BG, rect, border_radius=8)
        
        # Border
        border_color = COLOR_INPUT_BORDER if active else COLOR_INPUT_BORDER_INACTIVE
        pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=8)
        
        # Text or placeholder
        display_text = text if text else placeholder
        text_color = COLOR_TEXT if text else COLOR_TEXT_SECONDARY
        
        # Add blinking cursor if active
        if active and len(text) < 20:  # Limit length
            cursor_visible = (pygame.time.get_ticks() // 500) % 2
            if cursor_visible:
                display_text += "|"
        
        self.draw_text(display_text, self.font_medium, text_color, rect.x + 15, rect.y + 18)

    def draw_username_input_page(self):
        """Draw the username input page"""
        # Background gradient
        self.draw_gradient_rect(pygame.Rect(0, 0, self.screen_width, self.screen_height), 
                               COLOR_BG, (45, 50, 60))
        
        # Floating animation effect
        float_offset = math.sin(self.animation_time * 0.002) * 5
        
        # Main card
        card_rect = pygame.Rect(self.screen_width//2 - 300, self.screen_height//2 - 200 + float_offset, 
                               600, 400)
        self.draw_shadow_rect(card_rect, COLOR_SURFACE, 5)
        
        # Title
        self.draw_text("Number Guess Game", self.font_title, COLOR_PRIMARY, 
                      self.screen_width//2, self.screen_height//2 - 120 + float_offset, center=True)
        
        # Subtitle
        self.draw_text("Enter your username to start playing", self.font_medium, COLOR_TEXT_SECONDARY,
                      self.screen_width//2, self.screen_height//2 - 80 + float_offset, center=True)
        
        # Username input
        input_rect = pygame.Rect(self.screen_width//2 - 200, self.screen_height//2 - 20 + float_offset, 400, 60)
        self.draw_input_field(input_rect, self.username, self.username_input_active, "Enter username...")
        
        # Connect button
        btn_rect = pygame.Rect(self.screen_width//2 - 100, self.screen_height//2 + 60 + float_offset, 200, 50)
        self.draw_button(btn_rect, "Connect", enabled=len(self.username.strip()) > 0)
        
        # Error message
        if self.username_error:
            self.draw_text(self.username_error, self.font_small, COLOR_ERROR,
                          self.screen_width//2, self.screen_height//2 + 140 + float_offset, center=True)
        
        # Update button rect for click detection
        self.username_connect_btn = btn_rect

    def draw_connecting_page(self):
        """Draw the connecting page"""
        self.screen.fill(COLOR_BG)
        
        # Animated loading dots
        dots = ""
        dot_count = (pygame.time.get_ticks() // 500) % 4
        for i in range(dot_count):
            dots += "."
        
        self.draw_text("Connecting to server" + dots, self.font_big, COLOR_TEXT,
                      self.screen_width//2, self.screen_height//2, center=True)

    def draw_game_page(self):
        """Draw the main game page with enhanced UI"""
        # Background
        self.screen.fill(COLOR_BG)
        
        state = self.game_state
        if not state:
            self.draw_text("Loading game state...", self.font_big, COLOR_TEXT,
                        self.screen_width//2, self.screen_height//2, center=True)
            return
        
        # Header card
        header_rect = pygame.Rect(50, 30, self.screen_width - 100, 100)
        self.draw_shadow_rect(header_rect, COLOR_SURFACE)
        
        # Game state and message
        self.draw_text(f"Game State: {state.get('round_state', 'N/A')}", 
                    self.font_big, COLOR_PRIMARY, self.screen_width//2, 60, center=True)
        self.draw_text(state.get('round_message', ''), 
                    self.font_medium, COLOR_TEXT_SECONDARY, self.screen_width//2, 100, center=True)
        
        # Players section
        players_rect = pygame.Rect(50, 150, self.screen_width - 100, 280)
        self.draw_shadow_rect(players_rect, COLOR_SURFACE)
        
        # Players header
        self.draw_text("Players", self.font_big, COLOR_TEXT, 80, 170)
        
        y_pos = 220
        active_player_id = state.get('active_player_id')
        
        # Get usernames - prioritize server-provided ones, fallback to local storage
        server_usernames = state.get('player_usernames', {})
        
        for pid, pdata in state.get('players', {}).items():
            is_me = (pid == self.player_id)
            is_active_player = (pid == active_player_id)
            
            # Get username with proper fallback logic
            username = server_usernames.get(pid, self.player_usernames.get(pid, f"Player {pid[-4:]}"))
            display_name = f"{username} (You)" if is_me else username
            
            # Build player info string
            player_info = f"{display_name} | Score: {pdata['score']}"
            
            # Add round-specific info
            if state['round_state'] == 'WAITING_FOR_NUMBERS':
                raised_status = "✓" if pdata.get('raised_number') is not None else "✗"
                player_info += f" | Raised: {raised_status}"
            elif state['round_state'] == 'WAITING_FOR_GUESSES':
                guessed_status = "✓" if pdata.get('guess') is not None else "✗"
                player_info += f" | Guessed: {guessed_status}"
            elif state['round_state'] == 'ROUND_OVER':
                player_info += f" | Raised: {pdata.get('raised_number', '?')}"
                player_info += f" | Guessed: {pdata.get('guess', '?')}"
            
            # Active player indicator
            if is_active_player and state.get('round_state') != 'ROUND_OVER':
                pygame.draw.circle(self.screen, COLOR_SUCCESS, (90, y_pos + 10), 8)
            
            # Player text color
            text_color = COLOR_PRIMARY if is_me else (COLOR_ACCENT if is_active_player else COLOR_TEXT)
            
            # Draw with shadow for better readability
            self.draw_text(player_info, self.font_medium, COLOR_SHADOW, 111, y_pos + 1)
            self.draw_text(player_info, self.font_medium, text_color, 110, y_pos)
            
            y_pos += 40
        
        # Draw action buttons
        self.draw_action_buttons(state)
        self.draw_raise_animation()

    def draw_action_buttons(self, state):
        """Draw the action buttons section"""
        active_player_id = state.get('active_player_id')
        is_my_turn = (self.player_id == active_player_id)
        can_start_new = (state.get('round_state') == "ROUND_OVER")
        can_raise = (state.get('round_state') == "WAITING_FOR_NUMBERS" and is_my_turn)
        can_guess = (state.get('round_state') == "WAITING_FOR_GUESSES" and is_my_turn)
        
        if can_start_new:
            self.draw_button(self.btn_start_new_rect, "Start Next Round", enabled=True, style="secondary")
        else:
            # Raise buttons
            self.draw_button(self.btn_raise_1_rect, "Raise 1", enabled=can_raise, style="primary")
            self.draw_button(self.btn_raise_2_rect, "Raise 2", enabled=can_raise, style="primary")
            
            # Input field and guess button
            self.draw_input_field(self.input_box_rect, self.input_text, 
                                self.input_active and can_guess, "Enter guess...")
            self.draw_button(self.btn_guess_rect, "Submit Guess", enabled=can_guess, style="accent")

    def trigger_raise_animation(self, image):
        self.raise_animation["active"] = True
        self.raise_animation["image"] = image
        self.raise_animation["start_time"] = pygame.time.get_ticks()

    def draw_raise_animation(self):
        if not self.raise_animation["active"]:
            return
        
        now = pygame.time.get_ticks()
        elapsed = now - self.raise_animation["start_time"]

        if elapsed > self.raise_animation["duration"]:
            self.raise_animation["active"] = False
            return

        # Shake effect
        shake_magnitude = 10
        shake_offset_x = math.sin(now * 0.05) * shake_magnitude
        shake_offset_y = math.cos(now * 0.07) * shake_magnitude

        image = self.raise_animation["image"]
        image_rect = image.get_rect(center=(self.screen_width//2, self.screen_height//2))
        image_rect.x += int(shake_offset_x)
        image_rect.y += int(shake_offset_y)

        self.screen.blit(image, image_rect)

    def handle_username_events(self, event):
        """Handle events for username input page"""
        if event.type == pygame.KEYDOWN:
            if self.username_input_active:
                if event.key == pygame.K_RETURN:
                    if len(self.username.strip()) > 0:
                        self.connect_to_server()
                elif event.key == pygame.K_BACKSPACE:
                    self.username = self.username[:-1]
                    self.username_error = ""  # Clear error when typing
                elif len(self.username) < 20 and event.unicode.isprintable():
                    self.username += event.unicode
                    self.username_error = ""  # Clear error when typing
                    
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.username_connect_btn.collidepoint(event.pos):
                if len(self.username.strip()) > 0:
                    self.connect_to_server()

    def handle_game_events(self, event):
        """Handle events for game page"""
        state = self.game_state
        if not state:
            return

        active_player_id = state.get('active_player_id')
        is_my_turn = (self.player_id == active_player_id)
        can_start_new = (state.get('round_state') == "ROUND_OVER")
        can_raise = (state.get('round_state') == "WAITING_FOR_NUMBERS" and is_my_turn)
        can_guess = (state.get('round_state') == "WAITING_FOR_GUESSES" and is_my_turn)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if can_start_new:
                if self.btn_start_new_rect.collidepoint(event.pos):
                    self.send_action("start_new_round")
            else:
                if self.btn_raise_1_rect.collidepoint(event.pos) and can_raise:
                    self.send_action("raise_number", {"number": 1})
                    self.trigger_raise_animation(self.thumb_image)
                elif self.btn_raise_2_rect.collidepoint(event.pos) and can_raise:
                    self.send_action("raise_number", {"number": 2})
                    self.trigger_raise_animation(self.twothumbs_image)
                elif self.btn_guess_rect.collidepoint(event.pos) and can_guess:
                    self.submit_guess()
                
                # Input field click
                if self.input_box_rect.collidepoint(event.pos) and can_guess:
                    self.input_active = True
                else:
                    self.input_active = False
                    
        elif event.type == pygame.KEYDOWN:
            if self.input_active and can_guess:
                if event.key == pygame.K_RETURN:
                    self.submit_guess()
                elif event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif event.unicode.isdigit() and len(self.input_text) < 10:
                    self.input_text += event.unicode

    def handle_events(self):
        """Main event handler"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
                
            if self.current_state == self.STATE_USERNAME:
                self.handle_username_events(event)
            elif self.current_state == self.STATE_GAME:
                self.handle_game_events(event)

    def run(self):
        """Main game loop"""
        while self.running:
            self.animation_time = pygame.time.get_ticks()
            
            self.handle_events()
            
            # Draw current state
            if self.current_state == self.STATE_USERNAME:
                self.draw_username_input_page()
            elif self.current_state == self.STATE_CONNECTING:
                self.draw_connecting_page()
            elif self.current_state == self.STATE_GAME:
                self.draw_game_page()
            
            pygame.display.flip()
            self.clock.tick(60)  # Increased FPS for smoother animations
        
        # Cleanup
        if self.client_socket:
            self.client_socket.close()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = PygameClientApp()
    app.run()