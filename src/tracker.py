import logging
import socket
import threading
import os
from database import *

log_dir = '../log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'tracker.log')),
        logging.StreamHandler()
    ]
)

execute_sql_from_file('queries.sql')

class Tracker:
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.pieces = {} 

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
            drop_tables_from_database()
        finally:
            server.close()

    def handle_peer(self, conn):
        
        try:
            while True:
                data = conn.recv(1024).decode('utf-8')
                if data:
                    command, *params = data.split(' ')
                    if command == "REGISTER":
                        info_hash = params[0]
                        piece_index_list = list(map(int, params[1].split(',')))
                        peer_ip = params[2]
                        piece_registered = register_piece_in_database(info_hash, piece_index_list, peer_ip)
                        if not piece_registered:
                            conn.sendall(f"Failed to register {info_hash} from peer_ip {peer_ip}\n".encode('utf-8'))
                            continue
                        else: conn.sendall(f"Registered {info_hash} successfully!\n".encode('utf-8'))

                    elif command == "DOWNLOAD":
                        torrent_hash = params[0]
                        peers_list = get_peers_list_seeding_file_from_database(torrent_hash)
                        if not peers_list:
                            conn.sendall(f"No peers found for {torrent_hash}\n".encode('utf-8'))
                            continue
                        else: conn.sendall(f"Get peers list for {torrent_hash} are: {peers_list}\n".encode('utf-8'))
                    elif command == "EXIT":
                        peer_ip = params[0]
                        delete_peer_from_database(peer_ip)
                        logging.info(f"Peer {peer_ip} DISCONNECTED!!!")
                else:
                    break
        except Exception as e:
            logging.error(f"Error handling peer: {e}")

        finally:
            conn.close()

if __name__ == "__main__":
    tracker = Tracker()
    tracker.start()

