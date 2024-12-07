import socket
import threading
import os
import sys
import time
import logging
import logging.handlers
import random
import hashlib
import psutil
from torrentClient import *

log_dir = '../log'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

def setup_logging(peer_port):
    log_filename = os.path.join(log_dir, f"peer_{peer_port}.log")

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG) 
    file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def get_wifi_ip():
    for interface, addrs in psutil.net_if_addrs().items():
        if 'wlo1' in interface.lower() or 'wi-fi' in interface.lower():
            for addr in addrs:
                if addr.netmask != None:
                    return addr.address
    return '127.0.0.1'

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
        self.pieces_index_list = set() #set of piece index which are not downloaded

class Peer:
    def __init__(self, tracker_host, tracker_port):
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.tracker_url_list = [f"{self.tracker_host}:{self.tracker_port}"]
        self.files = {}

        self.peer_host = get_wifi_ip()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.peer_host, 0))
        self.server_socket.listen()

        self.peer_host, self.peer_port = self.server_socket.getsockname()
        self.peer_ip = f"{self.peer_host}:{self.peer_port}"
        setup_logging(self.peer_port)
        logging.info(f"Listening on {self.peer_host}:{self.peer_port}")
        threading.Thread(target=self.listen_for_requests).start()

    def ip_split(self, ip):
        host, port = ip.split(':')
        port = int(port)
        return host, port

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
                    with open(full_file_path, 'rb') as f:
                        f.seek(piece_index * piece_length)
                        piece = f.read(piece_length)
                        if piece:
                            conn.sendall(piece)
                            logging.debug(f"Sent piece {piece_index} of {file_name} to {conn.getpeername()}")
                        else:
                            logging.warning(f"Piece {piece_index} not available in {file_name}")
                else:
                    conn.sendall(f"{file_name} not found".encode('utf-8'))
                    
        except Exception as e:
            logging.error( f"Error handling request: {e}")
            
        finally:
            conn.close()

    def connect_to_tracker(self, tracker_host, tracker_port):
        self.tracker_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tracker_conn.connect((tracker_host, tracker_port))

    def calculate_piece_hash(self, piece_data: bytes) -> bytes:
        sha1 = hashlib.sha1()
        sha1.update(piece_data)
        return sha1.digest()

    def file_exists(self, full_file_path):
        return os.path.exists(full_file_path)
    
    def register_pieces(self, torrent_hash, piece_index_list, tracker_ip):
        try:
            if type(piece_index_list) != str:
                for piece_index in piece_index_list:
                    self.files[torrent_hash].pieces_index_list.discard(piece_index)
                piece_index_list_str = ",".join(map(str, piece_index_list))
            else :
                piece_index_list_str = piece_index_list
            ##################################
            tracker_host, tracker_port = self.ip_split(tracker_ip)
            self.connect_to_tracker(tracker_host, tracker_port)
            message = f"REGISTER {torrent_hash} {piece_index_list_str} {self.peer_ip}"
            self.tracker_conn.sendall(message.encode('utf-8'))
            response = self.tracker_conn.recv(1024).decode('utf-8')
            ##################################
            logging.debug(response)
            return response
        except Exception as e:
            logging.error(f"Error registering pieces for {torrent_hash} with {self.peer_ip}: {e}")
        finally:
            self.tracker_conn.close()
        
    def register_file(self, file_name, file_path):
        torrent = torrent_file_reader(file_name)
        try:
            piece_index_list = f":{torrent.pieces_count}" 
            self.files[torrent.info_hash] = File(torrent.file_name, file_path, torrent.file_size,
                                                 torrent.piece_length, torrent.pieces_count, 
                                                 torrent.pieces, torrent.info_hash)
            response = self.register_pieces(torrent.info_hash, piece_index_list,torrent.trackers_url_list[0])
            logging.info(response)
        except Exception as e:
            logging.error( f"Error connecting to tracker: {e}")
            return f"Failed to register file due to tracker connection issue."
        finally:
            self.tracker_conn.close()

    def download_piece_from_peer(self, torrent, file_path, piece_index, peer_ip):
        
        full_file_path = os.path.join(file_path, torrent.file_name)
        try:
            if not os.path.exists(file_path):
                os.makedirs(file_path)
        except FileExistsError:
            pass
        if self.file_exists(full_file_path): 
            mode = 'r+b'
        else:
            mode = 'wb'
        try:
            peer_host, peer_port = self.ip_split(peer_ip) 
            ##################################
            peer_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_conn.connect((peer_host, peer_port))
            peer_conn.sendall(f"GET {torrent.info_hash} {piece_index}".encode('utf-8'))
            piece = peer_conn.recv(4096)
            ##################################
            if piece:
                start_position = piece_index * torrent.piece_length
                hashpiece = self.calculate_piece_hash(piece)
                if hashpiece != torrent.pieces[piece_index]:
                    logging.error(f"Hash mismatch for piece {piece_index} of {torrent.info_hash} from {peer_ip}") 
                    return
                with open(full_file_path, mode) as f:
                    f.seek(start_position)
                    f.write(piece)
                logging.debug(f"Downloaded piece {piece_index} of {torrent.info_hash} from {peer_ip}")
            else:
                logging.error(f"No data received for piece {piece_index} of {torrent.file_name} from {peer_ip}")

        except Exception as e:
            logging.error(f"Error downloading piece {piece_index} of {torrent.info_hash} from {peer_ip}: {e}")

        finally:
            if hasattr(peer_conn, 'close') and peer_conn:
                peer_conn.close()

    def get_peers_list(self, torrent_hash, tracker_ip):
        try:
            ##################################
            tracker_host, tracker_port = self.ip_split(tracker_ip)
            self.connect_to_tracker(tracker_host, tracker_port)
            message = f"DOWNLOAD {torrent_hash}"
            self.tracker_conn.sendall(message.encode('utf-8'))
            response = self.tracker_conn.recv(1024).decode('utf-8')
            ##################################
            logging.debug(response)
            if response.startswith("Get peers list for "):
                peers_list_str = response.split("Get peers list for ")[1].split("are: ")[1]
                peers_list = [p.strip("' ") for p in peers_list_str.strip("[]\n").split(", ") if p]
            else:
                return []
            if self.peer_ip in peers_list:
                peers_list.remove(self.peer_ip)

            return peers_list
        except Exception as e:
            logging.error( f"Error getting peers list: {e}")
            return None
        finally:
            self.tracker_conn.close()

    def piece_selection_startergy(self, torrent_hash):
        piece_index_list = list(self.files[torrent_hash].pieces_index_list)
        random.shuffle( piece_index_list)
        return piece_index_list[:10]

    def peer_selection_startergy(self, torrent_hash, tracker_ip):
        peer_list = self.get_peers_list(torrent_hash, tracker_ip)
           
        random.shuffle(peer_list)
        return peer_list[:4]

    def download_complete(self, piece_index_list):
        return len(piece_index_list) == 0

    def download_stratergy(self, torrent, file_path):
        start_time = time.time()
        print("Downloading...")
        while not self.download_complete(self.files[torrent.info_hash].pieces_index_list):
            try:
                piece_index_list = self.piece_selection_startergy( torrent.info_hash )
                peer_ip_list = self.peer_selection_startergy( torrent.info_hash, torrent.trackers_url_list[0] )
                if len(peer_ip_list) == 0:
                    raise Exception("Peer list is empty")
                downloading_thread_pool = []
                turnAmount = min(len(piece_index_list), len(peer_ip_list))
                for i in range(turnAmount):
                    piece_index = piece_index_list[i]
                    peer_ip = peer_ip_list[i]
                    self.files[torrent.info_hash].pieces_index_list.discard(piece_index)
                    download_thread = threading.Thread(target=self.download_piece_from_peer, 
                                                        args=(torrent, file_path, piece_index, peer_ip))
                    downloading_thread_pool.append(download_thread)
                    download_thread.start()
                for downloading_thread in downloading_thread_pool:
                    downloading_thread.join()
                self.register_pieces(torrent.info_hash, piece_index_list[:turnAmount], torrent.trackers_url_list[0])
                    
            except Exception as e:
                logging.error( f"Error downloading pieces from peer {peer_ip}: {e}")

                full_file_path = os.path.join(file_path, torrent.file_name)
                if os.path.exists(full_file_path):
                    os.remove(full_file_path)
                    print(f"Deleted non-completed file at path {file_path}")

        logging.info( f"Download file completed in {round(time.time() - start_time, 2)} seconds")

    
    def download_file(self, file_name, file_path):
        try:
            torrent = torrent_file_reader( file_name )
            self.files[torrent.info_hash] = File(torrent.file_name, file_path, torrent.file_size, 
                                                 torrent.piece_length, torrent.pieces_count, 
                                                 torrent.pieces, torrent.info_hash)
            self.files[torrent.info_hash].pieces_index_list = set(range(torrent.pieces_count))

            self.download_stratergy(torrent, file_path) 
        except Exception as e:
            logging.error( f"Error downloading file: {e}")
        finally:
            if hasattr(self, 'tracker_conn') and self.tracker_conn:
                self.tracker_conn.close()

    def input_commands(self):
        logging.info(f"Welcome!!!")
        try:
            while True:
                print("\n-----------------------")
                print("Available commands:")
                print("1. Torrent - Create torrent file to become seeder")
                print("2. Seeding - Seeding file using torrent")
                print("3. Download - Download file by torrent")
                
                command = input("Enter command: ").strip().lower()

                if command == "1" or command == "torrent":
                    file_name = input("Enter file name to create torrent: ")
                    file_path = "." +input(f"Enter file path: ")
                    full_file_path = os.path.join(file_path, file_name)
                    if self.file_exists(full_file_path):
                        torrent_file_creater(full_file_path, self.tracker_url_list)
                    else:
                        logging.error( f"File {file_name} not found!")

                elif command == "2" or command == "seeding":
                    file_name = input("Enter name before .torrent to seed: ")
                    file_path = "." + input(f"Enter path of original file: ")
                    full_file_path = os.path.join(file_path, file_name)
                    full_torrent_file_path = os.path.join("../torrent", file_name + '.torrent')
                    
                    if self.file_exists(full_torrent_file_path):
                        if self.file_exists(full_file_path):
                            print("Registering file...")
                            self.register_file(file_name, file_path)
                        else:
                            logging.error( f"Original file not found!")
                    else:
                        logging.error( "Invalid torrent file.")

                elif command == "3" or command == "download":
                    file_name = input("Enter the torrent file_name to download: ")
                    file_path = "." + input(f"Enter path to download in: ")
                    full_torrent_file_path = os.path.join("../torrent", file_name + '.torrent')
                    if self.file_exists(full_torrent_file_path):
                        self.download_file(file_name, file_path)
                    else:
                        logging.error( "Invalid torrent file.")

                else:
                    logging.error( "Invalid command. Please try again.")
        except KeyboardInterrupt:
            logging.info(f"Exiting ...")
            self.exit_peer()
        except Exception as e:
            logging.error( f"Unexpected error occurred: {str(e)}")
        finally:
            logging.info("Closing server socket.")
        if hasattr(self, 'server_socket') and self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                logging.error( f"Error closing server socket: {str(e)}")
        sys.exit(0)

    def exit_peer(self):
        ##################################
        self.connect_to_tracker( self.tracker_host, self.tracker_port )
        message = f"EXIT {self.peer_ip}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        self.server_socket.close()
        ##################################

if __name__ == "__main__":
    ip = get_wifi_ip()
    peer = Peer(ip, 5000)
    peer.input_commands()

