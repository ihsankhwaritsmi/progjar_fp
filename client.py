import socket
import threading
import json
import tkinter as tk
from tkinter import messagebox

class GameClientApp:
    def __init__(self, master):
        self.master = master
        self.server_host = "localhost" # Change to server's IP if not running locally
        self.server_port = 8000
        self.player_id = None
        self.client_socket = None
        self.game_state = {}
        self.running = True
        
        self._setup_gui()
        
        # Start the network connection and listening thread
        self.network_thread = threading.Thread(target=self.network_loop, daemon=True)
        self.network_thread.start()

    def _setup_gui(self):
        self.master.title("Number Guess Game")
        self.master.geometry("600x450")
        self.master.configure(bg="#f0f0f0")

        self.status_label = tk.Label(self.master, text="Connecting...", font=("Arial", 16, "bold"), bg="#f0f0f0")
        self.status_label.pack(pady=(10, 5))

        self.round_info_label = tk.Label(self.master, text="", font=("Arial", 12), bg="#f0f0f0", wraplength=550)
        self.round_info_label.pack(pady=5)

        self.players_frame = tk.Frame(self.master, bg="#f0f0f0")
        self.players_frame.pack(pady=10, fill="x", padx=20)

        self.action_frame = tk.Frame(self.master, bg="#e3e3e3", padx=10, pady=10)
        self.action_frame.pack(pady=20)

        self.btn_raise_1 = tk.Button(self.action_frame, text="Raise 1", command=lambda: self.send_action("raise_number", {"number": 1}), font=("Arial", 12), width=15)
        self.btn_raise_1.grid(row=0, column=0, padx=10, pady=5)
        self.btn_raise_2 = tk.Button(self.action_frame, text="Raise 2", command=lambda: self.send_action("raise_number", {"number": 2}), font=("Arial", 12), width=15)
        self.btn_raise_2.grid(row=0, column=1, padx=10, pady=5)

        self.guess_entry = tk.Entry(self.action_frame, font=("Arial", 12), width=17)
        self.guess_entry.grid(row=1, column=0, padx=10, pady=5)
        self.btn_guess = tk.Button(self.action_frame, text="Submit Guess", command=self.submit_guess, font=("Arial", 12), width=15)
        self.btn_guess.grid(row=1, column=1, padx=10, pady=5)

        self.btn_start_new_round = tk.Button(self.master, text="Start Next Round", command=lambda: self.send_action("start_new_round"), font=("Arial", 12, "bold"), width=20)
        self.btn_start_new_round.pack(pady=10)
        
        self.update_gui() # Initial GUI state

    def network_loop(self):
        """Connects to the server and listens for messages."""
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_host, self.server_port))
        except (socket.error, ConnectionRefusedError) as e:
            print(f"Connection error: {e}")
            self.master.after(0, self.show_connection_error)
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
        
        print("Disconnected from server.")
        self.running = False
        self.master.after(0, self.show_connection_error, "Server connection lost.")

    def handle_server_message(self, message_str):
        """Parses a message from the server and updates state/GUI."""
        try:
            message = json.loads(message_str)
            msg_type = message.get("type")

            if msg_type == "welcome":
                self.player_id = message.get("player_id")
                self.master.after(0, self.master.title, f"Number Guess Game - {self.player_id}")
            
            elif msg_type == "game_state":
                self.game_state = message.get("data", {})
                self.master.after(0, self.update_gui)
            
            elif msg_type == "error":
                self.master.after(0, messagebox.showerror, "Server Error", message.get("message"))
                self.master.after(0, self.on_closing)

        except json.JSONDecodeError:
            print(f"Received invalid JSON: {message_str}")

    def send_action(self, action_type, data={}):
        """Sends a JSON action to the server."""
        if not self.client_socket or not self.running:
            return
        
        payload = {"action": action_type}
        payload.update(data)
        
        try:
            message = json.dumps(payload) + '\n'
            self.client_socket.sendall(message.encode('utf-8'))
        except socket.error as e:
            print(f"Failed to send action: {e}")

    def submit_guess(self):
        try:
            guess = int(self.guess_entry.get())
            self.send_action("make_guess", {"guess": guess})
            self.guess_entry.delete(0, tk.END)
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number for your guess.")

    def show_connection_error(self, message="Could not connect to the server. Is it running?"):
        if self.running: # Avoid showing error if window is already closing
            messagebox.showerror("Connection Failed", message)
            self.on_closing()

    def update_gui(self):
        """Updates all GUI elements based on the current game_state."""
        state = self.game_state
        if not state: # If no state yet, just disable all actions
            self.btn_raise_1.config(state=tk.DISABLED)
            self.btn_raise_2.config(state=tk.DISABLED)
            self.guess_entry.config(state=tk.DISABLED)
            self.btn_guess.config(state=tk.DISABLED)
            self.btn_start_new_round.config(state=tk.DISABLED)
            return

        self.status_label.config(text=f"Game State: {state.get('round_state', 'N/A')}")
        self.round_info_label.config(text=state.get('round_message', ''))
        
        for widget in self.players_frame.winfo_children():
            widget.destroy()

        my_player_data = state.get('players', {}).get(self.player_id, {})
        for pid, pdata in state.get('players', {}).items():
            is_me = (pid == self.player_id)
            player_text = f"{pid} (You)" if is_me else pid
            player_info = f"{player_text} | Score: {pdata['score']}"
            
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
            
            label = tk.Label(self.players_frame, text=player_info, font=("Arial", 11, "bold" if is_me else "normal"), bg="#f0f0f0")
            label.pack(anchor="w")

        can_raise = (state.get('round_state') == "WAITING_FOR_NUMBERS" and my_player_data.get('raised_number') is None)
        self.btn_raise_1.config(state=tk.NORMAL if can_raise else tk.DISABLED)
        self.btn_raise_2.config(state=tk.NORMAL if can_raise else tk.DISABLED)

        can_guess = (state.get('round_state') == "WAITING_FOR_GUESSES" and my_player_data.get('guess') is None)
        self.guess_entry.config(state=tk.NORMAL if can_guess else tk.DISABLED)
        self.btn_guess.config(state=tk.NORMAL if can_guess else tk.DISABLED)
        
        can_start_new = (state.get('round_state') == "ROUND_OVER")
        self.btn_start_new_round.config(state=tk.NORMAL if can_start_new else tk.DISABLED)

    def on_closing(self):
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = GameClientApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
