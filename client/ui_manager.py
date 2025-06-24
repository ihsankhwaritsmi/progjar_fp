# ui_manager.py

import pygame
import math
import config

class UIManager:
    def __init__(self, screen):
        self.screen = screen
        
        # Enhanced fonts
        self.font_title = pygame.font.Font(None, 56)
        self.font_big = pygame.font.Font(None, 42)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 24)

        # Load images for animation
        self.thumb_image = pygame.image.load("assets/thumb.png").convert_alpha()
        self.twothumbs_image = pygame.image.load("assets/twoThumbs.png").convert_alpha()

        # Resize images
        self.thumb_image = pygame.transform.scale(self.thumb_image, (800, 800))
        self.twothumbs_image = pygame.transform.scale(self.twothumbs_image, (800, 800))

        # Animation control
        self.raise_animation = {
            "active": False,
            "image": None,
            "start_time": 0,
            "duration": 1500
        }
        
        # UI Elements setup
        self.setup_ui_elements()

    def setup_ui_elements(self):
        # Username input page elements
        self.username_connect_btn_rect = pygame.Rect(config.SCREEN_WIDTH//2 - 100, config.SCREEN_HEIGHT//2 + 80, 200, 50)
        
        # Game UI elements
        button_width = 180
        button_height = 50
        padding = 20
        total_width = (button_width * 2) + padding
        start_x = (config.SCREEN_WIDTH - total_width) // 2
        y_start_actions = 480
        
        self.btn_raise_1_rect = pygame.Rect(start_x, y_start_actions, button_width, button_height)
        self.btn_raise_2_rect = pygame.Rect(start_x + button_width + padding, y_start_actions, button_width, button_height)
        
        y_row_2 = y_start_actions + button_height + padding
        self.input_box_rect = pygame.Rect(start_x, y_row_2, button_width, button_height)
        self.btn_guess_rect = pygame.Rect(start_x + button_width + padding, y_row_2, button_width, button_height)
        self.btn_start_new_rect = pygame.Rect(config.SCREEN_WIDTH//2 - button_width//2, y_row_2, button_width, button_height)

    def draw(self, app_state):
        """Main draw function, delegates based on current state."""
        if app_state.current_state == config.STATE_USERNAME:
            self.draw_username_input_page(app_state)
        elif app_state.current_state == config.STATE_CONNECTING:
            self.draw_connecting_page()
        elif app_state.current_state == config.STATE_GAME:
            self.draw_game_page(app_state)

    def draw_username_input_page(self, state):
        self.draw_gradient_rect(pygame.Rect(0, 0, config.SCREEN_WIDTH, config.SCREEN_HEIGHT), 
                               config.COLOR_BG, (45, 50, 60))
        
        float_offset = math.sin(state.animation_time * 0.002) * 5
        card_rect = pygame.Rect(config.SCREEN_WIDTH//2 - 300, config.SCREEN_HEIGHT//2 - 200 + float_offset, 600, 400)
        self.draw_shadow_rect(card_rect, config.COLOR_SURFACE, 5)
        
        self.draw_text("Number Guess Game", self.font_title, config.COLOR_PRIMARY, 
                      config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT//2 - 120 + float_offset, center=True)
        self.draw_text("Enter your username to start playing", self.font_medium, config.COLOR_TEXT_SECONDARY,
                      config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT//2 - 80 + float_offset, center=True)
        
        input_rect = pygame.Rect(config.SCREEN_WIDTH//2 - 200, config.SCREEN_HEIGHT//2 - 20 + float_offset, 400, 60)
        self.draw_input_field(input_rect, state.username, state.username_input_active, "Enter username...")
        
        btn_rect = pygame.Rect(config.SCREEN_WIDTH//2 - 100, config.SCREEN_HEIGHT//2 + 60 + float_offset, 200, 50)
        self.draw_button(btn_rect, "Connect", enabled=len(state.username.strip()) > 0)
        
        if state.username_error:
            self.draw_text(state.username_error, self.font_small, config.COLOR_ERROR,
                          config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT//2 + 140 + float_offset, center=True)
        self.username_connect_btn_rect = btn_rect

    def draw_connecting_page(self):
        self.screen.fill(config.COLOR_BG)
        dots = "." * ((pygame.time.get_ticks() // 500) % 4)
        self.draw_text("Connecting to server" + dots, self.font_big, config.COLOR_TEXT,
                      config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT//2, center=True)

    def draw_game_page(self, state_data):
        self.screen.fill(config.COLOR_BG)
        state = state_data.game_state
        if not state:
            self.draw_text("Loading game state...", self.font_big, config.COLOR_TEXT,
                        config.SCREEN_WIDTH//2, config.SCREEN_HEIGHT//2, center=True)
            return
        
        header_rect = pygame.Rect(50, 30, config.SCREEN_WIDTH - 100, 100)
        self.draw_shadow_rect(header_rect, config.COLOR_SURFACE)
        
        self.draw_text(f"Game State: {state.get('round_state', 'N/A')}", 
                    self.font_big, config.COLOR_PRIMARY, config.SCREEN_WIDTH//2, 60, center=True)
        self.draw_text(state.get('round_message', ''), 
                    self.font_medium, config.COLOR_TEXT_SECONDARY, config.SCREEN_WIDTH//2, 100, center=True)
        
        players_rect = pygame.Rect(50, 150, config.SCREEN_WIDTH - 100, 280)
        self.draw_shadow_rect(players_rect, config.COLOR_SURFACE)
        self.draw_text("Players", self.font_big, config.COLOR_TEXT, 80, 170)
        
        y_pos = 220
        active_player_id = state.get('active_player_id')
        server_usernames = state.get('player_usernames', {})
        
        for pid, pdata in state.get('players', {}).items():
            is_me = (pid == state_data.player_id)
            is_active_player = (pid == active_player_id)
            username = server_usernames.get(pid, state_data.player_usernames.get(pid, f"Player {pid[-4:]}"))
            display_name = f"{username} (You)" if is_me else username
            player_info = f"{display_name} | Score: {pdata['score']}"
            
            if state['round_state'] == 'WAITING_FOR_NUMBERS':
                player_info += f" | Raised: {'✓' if pdata.get('raised_number') is not None else '✗'}"
            elif state['round_state'] == 'WAITING_FOR_GUESSES':
                player_info += f" | Guessed: {'✓' if pdata.get('guess') is not None else '✗'}"
            elif state['round_state'] == 'ROUND_OVER':
                player_info += f" | Raised: {pdata.get('raised_number', '?')} | Guessed: {pdata.get('guess', '?')}"
            
            if is_active_player and state.get('round_state') != 'ROUND_OVER':
                pygame.draw.circle(self.screen, config.COLOR_SUCCESS, (90, y_pos + 10), 8)
            
            text_color = config.COLOR_PRIMARY if is_me else (config.COLOR_ACCENT if is_active_player else config.COLOR_TEXT)
            self.draw_text(player_info, self.font_medium, config.COLOR_SHADOW, 111, y_pos + 1)
            self.draw_text(player_info, self.font_medium, text_color, 110, y_pos)
            y_pos += 40
        
        self.draw_action_buttons(state_data)
        self.draw_raise_animation()
    
    def draw_action_buttons(self, state_data):
        state = state_data.game_state
        is_my_turn = (state_data.player_id == state.get('active_player_id'))
        can_start_new = (state.get('round_state') == "ROUND_OVER")
        can_raise = (state.get('round_state') == "WAITING_FOR_NUMBERS" and is_my_turn)
        can_guess = (state.get('round_state') == "WAITING_FOR_GUESSES" and is_my_turn)
        
        if can_start_new:
            self.draw_button(self.btn_start_new_rect, "Start Next Round", enabled=True, style="secondary")
        else:
            self.draw_button(self.btn_raise_1_rect, "Raise 1", enabled=can_raise)
            self.draw_button(self.btn_raise_2_rect, "Raise 2", enabled=can_raise)
            self.draw_input_field(self.input_box_rect, state_data.input_text, 
                                state_data.input_active and can_guess, "Enter guess...")
            self.draw_button(self.btn_guess_rect, "Submit Guess", enabled=can_guess, style="accent")

    def trigger_raise_animation(self, number):
        self.raise_animation["active"] = True
        self.raise_animation["image"] = self.thumb_image if number == 1 else self.twothumbs_image
        self.raise_animation["start_time"] = pygame.time.get_ticks()

    def draw_raise_animation(self):
        if not self.raise_animation["active"]: return
        elapsed = pygame.time.get_ticks() - self.raise_animation["start_time"]
        if elapsed > self.raise_animation["duration"]:
            self.raise_animation["active"] = False
            return

        shake_offset_x = math.sin(pygame.time.get_ticks() * 0.05) * 10
        shake_offset_y = math.cos(pygame.time.get_ticks() * 0.07) * 10
        image = self.raise_animation["image"]
        image_rect = image.get_rect(center=(config.SCREEN_WIDTH//2 + int(shake_offset_x), config.SCREEN_HEIGHT//2 + int(shake_offset_y)))
        self.screen.blit(image, image_rect)

    # --- Helper drawing functions (unchanged logic) ---
    def draw_text(self, text, font, color, x, y, center=False):
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        if center: text_rect.center = (x, y)
        else: text_rect.topleft = (x, y)
        self.screen.blit(text_surface, text_rect)

    def draw_gradient_rect(self, rect, color1, color2, vertical=True):
        if vertical:
            for y in range(rect.height):
                ratio = y / rect.height
                r = int(color1[0] + (color2[0] - color1[0]) * ratio)
                g = int(color1[1] + (color2[1] - color1[1]) * ratio)
                b = int(color1[2] + (color2[2] - color1[2]) * ratio)
                pygame.draw.line(self.screen, (r, g, b), (rect.x, rect.y + y), (rect.x + rect.width, rect.y + y))
    
    def draw_shadow_rect(self, rect, color, shadow_offset=3):
        shadow_rect = rect.copy()
        shadow_rect.move_ip(shadow_offset, shadow_offset)
        pygame.draw.rect(self.screen, config.COLOR_SHADOW, shadow_rect, border_radius=12)
        pygame.draw.rect(self.screen, color, rect, border_radius=12)

    def draw_button(self, rect, text, enabled=True, style="primary"):
        mouse_pos = pygame.mouse.get_pos()
        is_hovering = rect.collidepoint(mouse_pos)
        
        color_map = {
            "primary": (config.COLOR_PRIMARY, config.COLOR_PRIMARY_HOVER),
            "secondary": (config.COLOR_SECONDARY, config.COLOR_SECONDARY_HOVER),
            "accent": (config.COLOR_ACCENT, config.COLOR_ACCENT)
        }
        base_color, hover_color = color_map.get(style, (config.COLOR_PRIMARY, config.COLOR_PRIMARY_HOVER))
        btn_color = base_color if enabled else config.COLOR_TEXT_SECONDARY
        if is_hovering and enabled: btn_color = hover_color
        
        if enabled:
            shadow_rect = rect.copy(); shadow_rect.move_ip(2, 2)
            pygame.draw.rect(self.screen, config.COLOR_SHADOW, shadow_rect, border_radius=8)
        
        pygame.draw.rect(self.screen, btn_color, rect, border_radius=8)
        text_color = config.COLOR_TEXT if enabled else config.COLOR_TEXT_SECONDARY
        self.draw_text(text, self.font_medium, text_color, rect.centerx, rect.centery, center=True)

    def draw_input_field(self, rect, text, active, placeholder=""):
        pygame.draw.rect(self.screen, config.COLOR_INPUT_BG, rect, border_radius=8)
        border_color = config.COLOR_INPUT_BORDER if active else config.COLOR_INPUT_BORDER_INACTIVE
        pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=8)
        
        display_text = text if text else placeholder
        text_color = config.COLOR_TEXT if text else config.COLOR_TEXT_SECONDARY
        
        if active and len(text) < 20:
            if (pygame.time.get_ticks() // 500) % 2:
                display_text += "|"
        
        self.draw_text(display_text, self.font_medium, text_color, rect.x + 15, rect.y + (rect.height - self.font_medium.get_height()) // 2)