import socket
import threading
import os
import sys
import time
import logging

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('peer.log'),
        logging.StreamHandler()
    ]
)

class Peer:
    def __init__(self, peer_id, tracker_host, tracker_port):
        self.peer_id = peer_id
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.files = {}
        self.chunk_list = set()
        self.total_chunks = 0 

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('localhost', 0))
        self.server_socket.listen()
        self.peer_host, self.peer_port = self.server_socket.getsockname()
        logging.info(f"{self.peer_id} is listening on port {self.peer_port}")
        logging.info(f"peer_host:{self.peer_host}  peer_port:{self.peer_port}")
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
                filename, chunk_index = params[0], int(params[1])
                if filename in self.files:
                    with open(self.files[filename], 'rb') as f:
                        f.seek(chunk_index * 4096)
                        chunk = f.read(4096)
                        if chunk:
                            conn.sendall(chunk)
                            logging.info(f"Sent chunk {chunk_index} of {filename} to {conn.getpeername()}")
                        else:
                            logging.warning(f"Chunk {chunk_index} not available in {filename}")
                else:
                    conn.sendall(f"{filename} not found on {self.peer_id}".encode('utf-8'))
                    
        except Exception as e:
            logging.error(f"Error handling request: {e}")
            
        finally:
            conn.close() 

    def connect_to_tracker(self):
        self.tracker_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tracker_conn.connect((self.tracker_host, self.tracker_port))

    def file_exists(self, full_file_path):
        return os.path.exists(full_file_path)

    def register_file(self, filename, file_path):
        full_file_path = os.path.join(file_path, filename)
        self.files[filename] = full_file_path
        
        if self.file_exists(full_file_path):
            self.total_chunks = self.calculate_total_chunks(full_file_path)
            try:
                self.connect_to_tracker()
                message = f"REGISTER {filename} {self.total_chunks} {self.chunk_list} {self.peer_id}:{self.peer_port}"
                self.tracker_conn.sendall(message.encode('utf-8'))
                response = self.tracker_conn.recv(1024).decode('utf-8')
                logging.info(response)
            except Exception as e:
                logging.error(f"Error connecting to tracker: {e}")
                return f"Failed to register file {filename} due to tracker connection issue."
            finally:
                self.tracker_conn.close()
        else:
            logging.error(f"File {filename} does not exist on your folder {file_path}.")

    def calculate_total_chunks(self, full_file_path):
        chunk_size = 4096
        if not os.path.isfile(full_file_path):
            raise FileNotFoundError(f"The file does not exist.")
        with open(full_file_path, 'rb') as file:
            chunk_index = 0
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                if len(chunk) > 0:
                    self.chunk_list.add(chunk_index)
                chunk_index += 1
        logging.info(f"Chunk list: {self.chunk_list}")
        return len(self.chunk_list)
    
    def save_file_from_chunks(self, filename, file_path, chunks):
        full_file_path = os.path.join(file_path, filename)
        if not os.path.exists(file_path):
            os.makedirs(file_path)
        with open(full_file_path, 'wb') as f:
            for i in sorted(chunks.keys()):
                f.write(chunks[i])
        logging.info(f"File `{filename}` already downloaded!")
        self.register_file(filename, file_path)

    def request_file(self, filename, file_path):
        full_file_path = os.path.join(file_path, filename)

        self.connect_to_tracker()
        message = f"REQUEST {filename}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        response = self.tracker_conn.recv(1024).decode('utf-8')
        self.tracker_conn.close()

        if "Peers for" in response and "Total Chunks:" in response:
            peer_info = response.split("Peers for")[1].split(", Total Chunks:")
            peers_list_str = peer_info[0].strip()
            self.total_chunks = int(peer_info[1].strip())
            peers_list_str = peers_list_str.split(": ", 1)[-1].strip("[]")
            peer_list = [p.strip("[]' ") for p in peers_list_str.split(", ")]
            if len(peers_list_str) == 0:
                logging.warning("No peers available for the file.")
                return
            elif self.total_chunks == 0:
                logging.warning("No chunks available for the file.")
                return

            logging.info(response)

            chunks = {}
            start_time = time.time()
            last_response_time = start_time

            for chunk_index in range(self.total_chunks):
                peer_address = peer_list[chunk_index % len(peer_list)]
                host, port_str = peer_address.split(":")
                port = int(port_str)
                chunk = self.download_chunk_from_peer(filename, host, port, chunk_index)
                if chunk:
                    self.chunk_list.add(chunk_index)
                    chunks[chunk_index] = chunk
                else:
                    logging.warning(f"Failed to download chunk {chunk_index}")

                current_time = time.time()
                if current_time - last_response_time >= 5:
                    self.register_file(filename, full_file_path)
                    last_response_time = current_time

            self.save_file_from_chunks(filename, file_path, chunks)
        else:
            logging.error("Tracker response is not in expected format.")
            
    def download_chunk_from_peer(self, filename, host, port, chunk_index):
        peer_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_conn.connect(("localhost", port))
        peer_conn.sendall(f"GET {filename} {chunk_index}".encode('utf-8'))
        chunk = peer_conn.recv(4096)
        logging.info(f"Downloaded chunk {chunk_index} from {host}:{port}")
        peer_conn.close()
        return chunk

    def input_commands(self):
        logging.info(f"Welcome {self.peer_id}!")
        while True:
            try:
                print("\n-----------------------")
                print("Available commands:")
                print("1. publish - Publish file to tracker")
                print("2. download - Download file using torrent")
                print("3. exit - Exit the program")
                
                command = input("Enter command: ").strip().lower()

                if command == "1" or command == "publish":
                    filename = input("Enter the filename to publish: ")
                    file_path = input(f"Enter the full path of {filename}: ")
                    full_file_path = os.path.join(file_path, filename)
                    if self.file_exists(full_file_path):
                        self.register_file(filename, file_path)
                    else:
                        logging.error(f"File {filename} not found!")

                elif command == "2" or command == "download":
                    filename = input("Enter the filename to download: ")
                    file_path = input(f"Enter the full path to download in: ")
                    self.request_file(filename, file_path)

                elif command == "3" or command == "exit":
                    logging.info(f"Exiting {self.peer_id}...")
                    sys.exit(0)
                else:
                    logging.error("Invalid command. Please try again.")
            except KeyboardInterrupt:
                logging.info(f"Exiting {self.peer_id}...")
                sys.exit(0)

if __name__ == "__main__":
    peer_id = sys.argv[1] if len(sys.argv) > 1 else input("Enter your username: ").strip()
    peer = Peer(peer_id, "localhost", 5000)
    peer.input_commands()

