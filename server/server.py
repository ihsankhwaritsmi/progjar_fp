# file: server.py

import socket
import threading
import logging
import time
from game_logic import NumberGuessGame
from client_handler import ClientHandler

# Configure logging at the application's entry point
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Server(threading.Thread):
    """Main server class that listens for connections and manages client handlers."""
    def __init__(self, port=8000, required_players=2):
        super().__init__()
        self.port = port
        self.game = NumberGuessGame(required_players=required_players)
        self.clients = {}  # {connection: player_id}
        self.lock = threading.Lock()
        
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):
        """Binds the server and starts listening for client connections."""
        try:
            self.my_socket.bind(('0.0.0.0', self.port))
            self.my_socket.listen(5)
            logging.info(f"Server is listening on port {self.port}")

            while True:
                connection, client_address = self.my_socket.accept()
                logging.info(f"New connection accepted from {client_address}")
                client_thread = ClientHandler(connection, client_address, self.game, self.clients, self.lock)
                client_thread.start()
        except OSError as e:
            logging.error(f"Server error: {e}")
        except KeyboardInterrupt:
            logging.info("Server is shutting down.")
        finally:
            self.shutdown()
            
    def shutdown(self):
        """Closes all client connections and the main server socket."""
        with self.lock:
            for conn in self.clients:
                conn.close()
        self.my_socket.close()
        logging.info("Server has been shut down.")

def main():
    """Initializes and starts the server."""
    server_port = 8000
    server_instance = Server(port=server_port, required_players=2)
    server_instance.daemon = True
    server_instance.start()

    # Keep the main thread alive to listen for KeyboardInterrupt
    try:
        while server_instance.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutdown signal received.")
    finally:
        server_instance.shutdown()

if __name__ == "__main__":
    main()