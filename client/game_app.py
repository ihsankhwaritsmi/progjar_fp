import pygame
import sys
import config
from ui_manager import UIManager
from network_client import NetworkClient

class GameApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption("Number Guess Game")
        self.clock = pygame.time.Clock()
        self.running = True

        # State Management
        self.current_state = config.STATE_USERNAME
        self.username = ""
        self.username_input_active = True
        self.username_error = ""
        self.player_id = None
        self.game_state = {}
        self.status_message = ""
        self.player_usernames = {}
        self.input_text = ""
        self.input_active = False
        self.animation_time = 0

        # Components
        self.ui = UIManager(self.screen)
        self.network = NetworkClient(self)

    def run(self):
        while self.running:
            self.animation_time = pygame.time.get_ticks()
            self.handle_events()
            self.ui.draw(self)
            pygame.display.flip()
            self.clock.tick(config.FPS)
        self.cleanup()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if self.current_state == config.STATE_USERNAME:
                self.handle_username_events(event)
            elif self.current_state == config.STATE_GAME:
                self.handle_game_events(event)

    def handle_username_events(self, event):
        if event.type == pygame.KEYDOWN:
            if self.username_input_active:
                if event.key == pygame.K_RETURN:
                    self.try_connect()
                elif event.key == pygame.K_BACKSPACE:
                    self.username = self.username[:-1]
                    self.username_error = ""
                elif len(self.username) < 20 and event.unicode.isprintable():
                    self.username += event.unicode
                    self.username_error = ""
        elif event.type == pygame.MOUSEBUTTONDOWN:
            connect_btn_rect = self.ui.get_connect_button_rect()
            if connect_btn_rect and connect_btn_rect.collidepoint(event.pos):
                self.try_connect()

    def handle_game_events(self, event):
        if not self.game_state: return
        
        state = self.game_state
        is_my_turn = (self.player_id == state.get('active_player_id'))
        can_start_new = (state.get('round_state') == "ROUND_OVER")
        can_raise = (state.get('round_state') == "WAITING_FOR_NUMBERS" and is_my_turn)
        # Check if player is designated guesser (their turn)
        is_guesser = False
        if state.get('round_state') == "WAITING_FOR_GUESSES" and state.get('turn_order'):
             guesser_idx = (state.get('current_round', 1) - 1) % len(state.get('turn_order'))
             if guesser_idx < len(state.get('turn_order')):
                 guesser_id = state['turn_order'][guesser_idx]
                 is_guesser = (self.player_id == guesser_id)

        can_guess = (state.get('round_state') == "WAITING_FOR_GUESSES" and is_guesser)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if can_start_new and self.ui.btn_start_new_rect.collidepoint(event.pos):
                self.network.send_action("start_new_round")
            elif can_raise and self.ui.btn_raise_1_rect.collidepoint(event.pos):
                self.network.send_action("raise_number", {"number": 1})
                self.ui.trigger_raise_animation(1)
            elif can_raise and self.ui.btn_raise_2_rect.collidepoint(event.pos):
                self.network.send_action("raise_number", {"number": 2})
                self.ui.trigger_raise_animation(2)
            elif can_guess and self.ui.btn_guess_rect.collidepoint(event.pos):
                self.submit_guess()
            
            self.input_active = can_guess and self.ui.input_box_rect.collidepoint(event.pos)
        
        elif event.type == pygame.KEYDOWN:
            if self.input_active and can_guess:
                if event.key == pygame.K_RETURN:
                    self.submit_guess()
                elif event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif event.unicode.isdigit() and len(self.input_text) < 10:
                    self.input_text += event.unicode

    def try_connect(self):
        if len(self.username.strip()) > 0:
            self.username_error = ""
            self.network.connect()

    def submit_guess(self):
        if self.input_text:
            try:
                self.network.send_action("make_guess", {"guess": int(self.input_text)})
                self.input_text = ""
                self.input_active = False
            except ValueError:
                self.input_text = ""

    def process_server_message(self, message):
        msg_type = message.get("type")
        if msg_type == "game_state":
            new_state = message.get("data", {})
            if "player_usernames" in new_state:
                self.player_usernames.update(new_state["player_usernames"])
            self.game_state = new_state
        elif msg_type == "error":
            error_msg = message.get('message', 'Unknown error')
            if self.current_state == config.STATE_CONNECTING:
                self.handle_connection_error(error_msg)
            else:
                self.status_message = f"Server Error: {error_msg}"
            print(f"Server Error: {error_msg}")

    def handle_connection_error(self, error_msg):
        self.username_error = error_msg
        self.current_state = config.STATE_USERNAME
        print(error_msg)

    def cleanup(self):
        print("Cleaning up and closing.")
        self.network.close()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = GameApp()
    app.run()
