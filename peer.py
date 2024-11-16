import socket
import threading
import os
import sys
import time
import logging
from torrentClient import *

log_dir = './log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'peer.log')),
        logging.StreamHandler()
    ]
)
class File:
    def __init__(self, file_name, file_path, file_size, piece_length, pieces_count, pieces, info_hash):
        self.file_name = file_name
        self.file_path = file_path
        self.file_size = file_size
        self.piece_length   = piece_length
        self.pieces_count = pieces_count
        self.pieces = pieces
        self.info_hash = info_hash
        self.pieces_hash = {}

class Peer:
    def __init__(self, peer_id, tracker_host, tracker_port):
        self.peer_id = peer_id
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.files = {}

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('localhost', 0))
        self.server_socket.listen()
        self.peer_host, self.peer_port = self.server_socket.getsockname()
        self.peer_ip = f"{self.peer_host}:{self.peer_port}"
        logging.info(f"{self.peer_id} is listening on {self.peer_host}:{self.peer_port}")
        threading.Thread(target=self.listen_for_requests).start()

    def listen_for_requests(self):
        while True:
            conn, addr = self.server_socket.accept()
            threading.Thread(target=self.handle_request, args=(conn,)).start()

    def handle_request(self, conn):
        try:
            data = conn.recv(1024).decode('utf-8')
            command, *params = data.split()
            if command == "GET":
                torrent_hash, piece_index = params[0], int(params[1])
                piece_length = self.files[torrent_hash].piece_length
                file_name = self.files[torrent_hash].file_name
                if torrent_hash in self.files:
                    full_file_path = os.path.join(self.files[torrent_hash].file_path, file_name)
                    print(full_file_path)
                    with open(full_file_path, 'rb') as f:
                        f.seek(piece_index * piece_length)
                        piece = f.read(piece_length)
                        if piece:
                            conn.sendall(piece)
                            logging.info(f"Sent piece {piece_index} of {file_name} to {conn.getpeername()}")
                        else:
                            logging.warning(f"Piece {piece_index} not available in {file_name}")
                else:
                    conn.sendall(f"{file_name} not found on {self.peer_id}".encode('utf-8'))
                    
        except Exception as e:
            logging.error(f"Error handling request: {e}")
            
        finally:
            conn.close() 

    def connect_to_tracker(self):
        self.tracker_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tracker_conn.connect((self.tracker_host, self.tracker_port))
    def split_ip(self, peer_ip):
        return peer_ip.split(':')
    def file_exists(self, full_file_path):
        return os.path.exists(full_file_path)

    def register_pieces(self, torrent_hash, piece_index_list, peer_ip):
        peer_host, peer_port = peer_ip.split(':')
        peer_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_conn.connect((peer_host, peer_port))
        peer_conn.sendall(f"REGISTER {torrent_hash} {','.join(map(str, piece_index_list))}".encode('utf-8'))
        response = peer_conn.recv(1024).decode('utf-8')
        logging.info(response)
        peer_conn.close()

    def save_file_from_pieces(self, file_name, file_path, pieces):
        full_file_path = os.path.join(file_path, file_name)
        if not os.path.exists(file_path):
            os.makedirs(file_path)
        with open(full_file_path, 'wb') as f:
            for i in sorted(pieces.keys()):
                f.write(pieces[i])
        logging.info(f"File `{file_name}` already downloaded!")
        self.register_file(file_name, file_path)
           
    def download_piece_from_peer(self, torrent_hash, piece_index, peer_ip):
        peer_host, peer_port = peer_ip.split(':')
        peer_port = int(peer_port)
        try:
            ##################################
            peer_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_conn.connect((peer_host, peer_port))
            
            peer_conn.sendall(f"GET {torrent_hash} {piece_index}".encode('utf-8'))
            piece = peer_conn.recv(4096)
            logging.info(f"Downloaded piece {piece_index} of {torrent_hash} from {peer_ip}")
            ##################################
        except Exception as e:
            logging.error(f"Error downloading piece {piece_index} of {torrent_hash} from {peer_ip}: {e}")
            piece = None
        finally:
            if hasattr(peer_conn, 'close') and peer_conn:
                peer_conn.close()
            return piece
    def get_pieces_from_other_peer(self, torrent, peers_list, file_path):
        pieces = {}
        start_time = time.time()
        last_response_time = start_time
        piece_index_list = []

        for piece_index in range(torrent.pieces_count):
            peer_ip = peers_list[piece_index % len(peers_list)]
            piece = self.download_piece_from_peer(torrent.info_hash, piece_index, peer_ip)
            print(piece)
            if piece:
                pieces[piece_index] = piece
                piece_index_list.append(piece_index)
            else:
                logging.warning(f"Failed to download piece {piece_index}")

            current_time = time.time()
            if current_time - last_response_time >= 5:
                self.register_pieces(torrent.info_hash, piece_index_list, self.peer_ip)
                last_response_time = current_time
            self.save_file_from_pieces(torrent.file_name, file_path, pieces)

    def register_file(self, torrent_full_file_path, file_path):
        torrent = torrent_file_reader(torrent_full_file_path)
        try:
            piece_index_list = [i for i in range(torrent.pieces_count)]
            piece_index_str = ",".join(map(str, piece_index_list))
            ##################################
            self.connect_to_tracker()
            message = f"REGISTER {torrent.info_hash} {piece_index_str} {self.peer_host}:{self.peer_port}"
            self.tracker_conn.sendall(message.encode('utf-8'))
            response = self.tracker_conn.recv(1024).decode('utf-8')
            logging.info(response)
            ##################################
            self.files[torrent.info_hash] = File(torrent.file_name, file_path, torrent.file_size,
                                                 torrent.piece_length, torrent.pieces_count, 
                                                 torrent.pieces, torrent.info_hash)
        except Exception as e:
            logging.error(f"Error connecting to tracker: {e}")
            return f"Failed to register file due to tracker connection issue."
        finally:
            self.tracker_conn.close()
 
    def download_file(self, full_file_path):
        try:
            torrent = torrent_file_reader(full_file_path)
            torrent_hash = torrent.info_hash
            ##################################
            self.connect_to_tracker()
            message = f"DOWNLOAD {torrent_hash}"
            self.tracker_conn.sendall(message.encode('utf-8'))
            response = self.tracker_conn.recv(1024).decode('utf-8')
            logging.info(response)
            ##################################
            if response.startswith("Downloading"):
                peers_list_str = response.split("Downloading ")[1].split(": ")[1]
                peers_list = [p.strip("' ") for p in peers_list_str.strip("[]\n").split(", ") if p]

                file_path = os.path.dirname(full_file_path)
                self.get_pieces_from_other_peer(torrent, peers_list, file_path)
        except Exception as e:
            logging.error(f"Error downloading file: {e}")
        finally:
            if hasattr(self, 'tracker_conn') and self.tracker_conn:
                self.tracker_conn.close()

    def exit_peer(self):
        ##################################
        self.connect_to_tracker()
        message = f"EXIT {self.peer_host}:{self.peer_port}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        self.server_socket.close()
        ##################################

    def input_commands(self):
        logging.info(f"Welcome {self.peer_id}!")
        try:
            while True:
                print("\n-----------------------")
                print("Available commands:")
                print("1. Torrent - Create torrent file to become seeder")
                print("2. Seeding - Seeding file using torrent")
                print("3. Download - Download file by torrent")
                
                command = input("Enter command: ").strip().lower()

                if command == "1" or command == "torrent":
                    filename = input("Enter file name to create torrent: ")
                    file_path = input(f"Enter file path: ")
                    full_file_path = os.path.join(file_path, filename)
                    if self.file_exists(full_file_path):
                        torrent_file_creater(full_file_path)
                    else:
                        logging.error(f"File {filename} not found!")

                elif command == "2" or command == "seeding":
                    torrent_name = input("Enter name before .torrent to seed: ")
                    file_path = input(f"Enter path of original file: ")
                    full_file_path = os.path.join(file_path, torrent_name)
                    torrent_path = os.path.join('./torrent', torrent_name + '.torrent')
                    
                    if self.file_exists(torrent_path) and self.file_exists(full_file_path):
                        self.register_file(torrent_path, file_path)
                    else:
                        logging.error("Invalid torrent file.")

                elif command == "3" or command == "download":
                    torrent_name = input("Enter the torrent file_name to download: ")
                    file_path = input(f"Enter the full path to download in: ")
                    full_file_path = os.path.join("torrent", torrent_name + '.torrent')
                    if self.file_exists(full_file_path):
                        self.download_file(full_file_path)
                    else:
                        logging.error("Invalid torrent file.")

                else:
                    logging.error("Invalid command. Please try again.")
        except KeyboardInterrupt:
            logging.info(f"Exiting {self.peer_id}...")
            self.exit_peer()
        except Exception as e:
            logging.error(f"Unexpected error occurred: {str(e)}")
        finally:
            logging.info("Closing server socket.")
        if hasattr(self, 'server_socket') and self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                logging.error(f"Error closing server socket: {str(e)}")
        sys.exit(0)

if __name__ == "__main__":
    peer_id = sys.argv[1] if len(sys.argv) > 1 else input("Enter your username: ").strip()
    peer = Peer(peer_id, "localhost", 5000)
    peer.input_commands()

