import socket
import threading

class Tracker:
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.files = {}  # Cấu trúc: {'filename': [list of peers]}
    
    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.host, self.port))
        server.listen()
        print("Tracker is running...")
        
        while True:
            conn, addr = server.accept()
            print(f"Connected by {addr}")
            threading.Thread(target=self.handle_peer, args=(conn,)).start()

    def handle_peer(self, conn):
        try:
            while True:
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break
                command, *params = data.split()
                
                if command == "REGISTER":
                    filename, peer = params
                    self.register_file(filename, peer)
                    conn.sendall(f"{filename} registered by {peer}\n".encode('utf-8'))
                
                elif command == "REQUEST":
                    filename = params[0]
                    peers = self.get_peers(filename)
                    conn.sendall(f"Peers for {filename}: {peers}\n".encode('utf-8'))
        
        finally:
            conn.close()

    def register_file(self, filename, peer):
        if filename not in self.files:
            self.files[filename] = []
        if peer not in self.files[filename]:
            self.files[filename].append(peer)
        print(f"Registered file {filename} from peer {peer}")

    def get_peers(self, filename):
        return self.files.get(filename, [])

# Khởi động Tracker
if __name__ == "__main__":
    tracker = Tracker()
    tracker.start()
