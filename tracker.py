import logging
import socket
import threading
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tracker.log'),
        logging.StreamHandler()
    ]
)

try:
    conn = psycopg2.connect(dbname="", user="postgres", password="12345678", host="localhost", port="5432")
    cur = conn.cursor()
    logging.info("Database connected successfully.")
except Exception as e:
    logging.error(f"Error connecting to database: {e}")
    exit(1)

class Tracker:
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.files = {}  # multiple arrays contain peers info base on filename
        self.chunks = {}  # multiple arrays contain chunks info base on filename

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen()
        logging.info("Tracker is running...")

        try:
            while True:
                conn, addr = server.accept()
                logging.info(f"Connected by {addr}!")

                threading.Thread(target=self.handle_peer, args=(conn,)).start()
        except KeyboardInterrupt:
            logging.info("Tracker shutdown requested.")
        finally:
            server.close()

    def handle_peer(self, conn):
        try:
            while True:
                data = conn.recv(1024).decode('utf-8')
                if data:
                    command, *params = data.split()
                    filename = params[0]
                    if command == "REGISTER":
                        total_chunks = int(params[1])
                        chunk_list = params[2:-1]
                        peer = params[-1]
                        logging.info(f"Registering file {filename} with {total_chunks} chunks from peer_id: {peer}")
                        self.register_file(filename, total_chunks, peer)
                        conn.sendall(f"{filename} registered with {total_chunks} chunks by {peer}\n".encode('utf-8'))

                    elif command == "REQUEST":
                        peers, total_chunks = self.get_peers_and_chunks(filename)
                        conn.sendall(f"Peers for {filename}: {peers}, Total Chunks: {total_chunks}\n".encode('utf-8'))
                else:
                    break
        except Exception as e:
            logging.error(f"Error handling peer: {e}")

        finally:
            conn.close()

    def register_file(self, filename, total_chunks, peer):
        if filename not in self.chunks:
            self.chunks[filename] = total_chunks
        # initialize peer list in files array if it doesn't exist
        if filename not in self.files:
            self.files[filename] = []

        # add peer to peer list
        if peer not in self.files[filename]:
            self.files[filename].append(peer)

        logging.info(f"Registered file {filename} with {total_chunks} chunks from peer {peer}")

    def get_peers_and_chunks(self, filename):
        peers = self.files.get(filename, [])
        if peers:
            total_chunks = self.chunks.get(filename, 0)
            return peers, total_chunks
        return [], 0

if __name__ == "__main__":
    tracker = Tracker()
    tracker.start()

