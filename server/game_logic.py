# file: game_logic.py

import threading
import logging

class NumberGuessGame:
    """Manages the state and rules of the Number Guess Game."""
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
        self.player_usernames = {}

    def _get_current_player_id(self):
        if not self.turn_order or self.current_turn_index >= len(self.turn_order):
            return None
        return self.turn_order[self.current_turn_index]

    def _update_round_state(self, new_state, message=""):
        self.round_state = new_state
        self.round_message = message
        logging.info(f"Game State Updated: {self.round_state} - {self.round_message}")

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
            
            logging.info(f"Player {player_id} ({username}) joined. Total players: {len(self.players)}/{self.required_players}.")
            
            if len(self.players) == self.required_players:
                self.start_new_round()
            else:
                remaining = self.required_players - len(self.players)
                self.round_message = f"Welcome {username or player_id}! Waiting for {remaining} more player(s)."
            return {"status": "ok"}

    def remove_player(self, player_id):
        with self.lock:
            if player_id not in self.players:
                return False
            
            username = self.player_usernames.get(player_id, player_id)
            was_current_turn = (player_id == self._get_current_player_id())
            
            del self.players[player_id]
            self.turn_order.remove(player_id)
            if player_id in self.player_usernames:
                del self.player_usernames[player_id]
            
            logging.info(f"Player {username} (ID: {player_id}) left. Total players: {len(self.players)}")
            
            if self.round_state != "WAITING_FOR_PLAYERS" and len(self.players) < self.required_players:
                self._update_round_state("WAITING_FOR_PLAYERS", "A player disconnected. Waiting for players.")
                self.current_round = 0
                for pid in self.players:
                    self.players[pid] = {'score': 0, 'raised_number': None, 'guess': None}
            elif was_current_turn:
                self._check_for_state_transition()
            return True

    def start_new_round(self):
        self.current_round += 1
        self.actual_total = 0
        for player_id in self.players:
            self.players[player_id].update({'raised_number': None, 'guess': None})

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
            username = self.player_usernames.get(player_id, player_id)
            
            if self.round_state == "WAITING_FOR_NUMBERS":
                self._handle_raise_action(player_id, action, action_data.get("number"))
            
            elif self.round_state == "WAITING_FOR_GUESSES":
                self._handle_guess_action(player_id, username, action, action_data.get("guess"))

            elif action == "start_new_round" and self.round_state == "ROUND_OVER":
                self.start_new_round()

    def _handle_raise_action(self, player_id, action, number):
        if player_id != self._get_current_player_id() or action != "raise_number":
            return
        
        if number in [1, 2] and self.players[player_id]['raised_number'] is None:
            self.players[player_id]['raised_number'] = number
            username = self.player_usernames.get(player_id, player_id)
            logging.info(f"Player {username} (ID: {player_id}) raised: {number}")
            self.current_turn_index += 1
            self._check_for_state_transition()

    def _handle_guess_action(self, player_id, username, action, guess):
        designated_guesser_index = (self.current_round - 1) % len(self.turn_order)
        designated_guesser_id = self.turn_order[designated_guesser_index]
        
        if player_id != designated_guesser_id or action != "make_guess":
            return
        
        min_guess, max_guess = len(self.players), len(self.players) * 2
        if not (isinstance(guess, int) and min_guess <= guess <= max_guess):
            return

        self.players[player_id]['guess'] = guess
        logging.info(f"Player {username} (ID: {player_id}) submitted guess: {guess}")
        
        if guess == self.actual_total:
            self.players[player_id]['score'] += 1
            result_message = f"Round {self.current_round} Over! {username} guessed correctly ({guess}) and wins!"
        else:
            result_message = f"Round {self.current_round} Over! {username} guessed {guess}, but the total was {self.actual_total}."
        
        self._update_round_state("ROUND_OVER", result_message)
        logging.info(result_message)

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
            else:  # Still waiting for other players
                next_player_id = self._get_current_player_id()
                next_username = self.player_usernames.get(next_player_id, next_player_id)
                self._update_round_state("WAITING_FOR_NUMBERS", f"Waiting for {next_username} to raise a number.")
                
    def get_state(self):
        with self.lock:
            active_player_id = None
            if self.round_state == 'WAITING_FOR_NUMBERS':
                active_player_id = self._get_current_player_id()
            elif self.round_state == 'WAITING_FOR_GUESSES':
                designated_guesser_index = (self.current_round - 1) % len(self.turn_order)
                active_player_id = self.turn_order[designated_guesser_index]
            
            # Create a safe copy of player data for display
            display_players = {pid: data.copy() for pid, data in self.players.items()}
            if self.round_state != "ROUND_OVER":
                for pid, data in display_players.items():
                    if data.get('guess') is not None: data['guess'] = '?'
                    # Optionally hide raised numbers until round over
                    # if data.get('raised_number') is not None: data['raised_number'] = '?'

            return {
                "current_round": self.current_round,
                "round_state": self.round_state,
                "round_message": self.round_message,
                "players": display_players,
                "actual_total": self.actual_total if self.round_state == "ROUND_OVER" else None,
                "required_players": self.required_players,
                "active_player_id": active_player_id,
                "player_usernames": self.player_usernames
            }