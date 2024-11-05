import socket
import threading

class Tracker:
    def __init__(self, host='127.0.0.1', port=5000):
        self.host = host
        self.port = port
        self.files = {}  # Cấu trúc: {'filename': [list of peers]}
        self.chunks = {}  # Cấu trúc: {'filename': total_chunks}
    
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
                    filename, total_chunks, peer = params
                    total_chunks = int(total_chunks)  # Chuyển đổi số chunk sang kiểu int
                    self.register_file(filename, total_chunks, peer)
                    conn.sendall(f"{filename} registered with {total_chunks} chunks by {peer}\n".encode('utf-8'))
                
                elif command == "REQUEST":
                    filename = params[0]
                    peers, total_chunks = self.get_peers_and_chunks(filename)
                    conn.sendall(f"Peers for {filename}: {peers}, Total Chunks: {total_chunks}\n".encode('utf-8'))
        
        finally:
            conn.close()

    def register_file(self, filename, total_chunks, peer):
        # Lưu thông tin số chunk cho file
        if filename not in self.chunks:
            self.chunks[filename] = total_chunks
        
        # Đảm bảo file đã có trong self.files và thêm peer vào danh sách nếu chưa có
        if filename not in self.files:
            self.files[filename] = []
        if peer not in self.files[filename]:
            self.files[filename].append(peer)
        
        print(f"Registered file {filename} with {total_chunks} chunks from peer {peer}")

    def get_peers(self, filename):
        return self.files.get(filename, [])

    def get_peers_and_chunks(self, filename):
        # Lấy danh sách các peer và tổng số chunk của file
        peers = self.files.get(filename, [])
        total_chunks = self.chunks.get(filename, 0)
        return peers, total_chunks
# Khởi động Tracker
if __name__ == "__main__":
    tracker = Tracker()
    tracker.start()
