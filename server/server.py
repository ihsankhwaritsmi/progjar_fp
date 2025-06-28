import socket
import threading
import logging
import time
from http import HttpServer
from game_logic import NumberGuessGame

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ProcessTheClient(threading.Thread):
    def __init__(self, connection, address, http_server):
        self.connection = connection
        self.address = address
        self.http_server = http_server
        threading.Thread.__init__(self)

    def run(self):
        header_buffer = b""
        while b'\r\n\r\n' not in header_buffer:
            try:
                data = self.connection.recv(1024)
                if not data:
                    break
                header_buffer += data
            except (socket.timeout, ConnectionResetError):
                logging.warning(f"Connection timed out or was reset by {self.address}. Partial data received: {header_buffer!r}")
                break
        
        if b'\r\n\r\n' not in header_buffer:
            logging.warning(f"Incomplete headers received from {self.address}. Discarding request.")
            self.connection.close()
            return

        try:
            header_part, body_part = header_buffer.split(b'\r\n\r\n', 1)
            headers = header_part.decode('utf-8')
        except (ValueError, UnicodeDecodeError):
            logging.warning(f"Could not decode headers from {self.address}")
            self.connection.close()
            return

        content_length = 0
        for line in headers.split('\r\n'):
            if line.lower().startswith('content-length:'):
                try:
                    content_length = int(line.split(':', 1)[1].strip())
                except (ValueError, IndexError):
                    content_length = 0
                break
        
        while len(body_part) < content_length:
            try:
                bytes_to_read = content_length - len(body_part)
                if bytes_to_read <= 0:
                    break
                data = self.connection.recv(bytes_to_read)
                if not data:
                    break
                body_part += data
            except (socket.timeout, ConnectionResetError):
                break

        full_request = headers + '\r\n\r\n' + body_part.decode('utf-8', 'ignore')
        
        logging.info(f"Processing request from {self.address}: {full_request.strip()}")
        hasil = self.http_server.proses(full_request)
        
        self.connection.sendall(hasil)
        self.connection.close()

class Server(threading.Thread):
    def __init__(self, port=8000, required_players=2):
        super().__init__()
        self.port = port
        self.game = NumberGuessGame(required_players=required_players)
        self.http_server = HttpServer(self.game)
        self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.my_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = True
        
    def run(self):
        self.my_socket.bind(('0.0.0.0', self.port))
        self.my_socket.listen(5)
        logging.info(f"Server is listening on port {self.port}")

        while self.running:
            try:
                connection, client_address = self.my_socket.accept()
                logging.info(f"Connection from {client_address}")
                # IMPORTANT!!! Prevent hanging client
                connection.settimeout(15.0)
                clt = ProcessTheClient(connection, client_address, self.http_server)
                clt.start()
            except socket.error:
                if self.running:
                    logging.info("Server socket closed.")
                break

    def shutdown(self):
        self.running = False
        # To unblock the accept() call
        try:
            # Create a dummy connection to the server to unblock the accept call
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', self.port))
        except Exception as e:
            logging.debug(f"Dummy connection during shutdown failed: {e}")

        self.my_socket.close()
        logging.info("Server has been shut down.")


def main():
    """Initializes and starts the server."""
    server_port = 8000
    server_instance = Server(port=server_port, required_players=2)
    server_instance.daemon = True
    server_instance.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutdown signal received.")
    finally:
        server_instance.shutdown()
        server_instance.join()

if __name__ == "__main__":
    main()
