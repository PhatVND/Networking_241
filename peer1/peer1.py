import socket
import threading
import os

class Peer:
    def __init__(self, peer_id, tracker_host='127.0.0.1', tracker_port=5000):
        self.peer_id = peer_id
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.files = {}
        
        # Khởi tạo socket cho peer để lắng nghe các yêu cầu tải file từ peers khác
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('localhost', 0))
        self.server_socket.listen()
        self.peer_host, self.peer_port = self.server_socket.getsockname()
        print(f"{self.peer_id} is listening on port {self.peer_port}")
        
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
                filename, chunk_index = params[0], int(params[1])  # Nhận chỉ số chunk
                if filename in self.files:
                    with open(self.files[filename], 'rb') as f:
                        # Tìm vị trí chunk và đọc dữ liệu
                        f.seek(chunk_index * 4096)
                        chunk = f.read(4096)
                        if chunk:
                            conn.sendall(chunk)
                            print(f"Sent chunk {chunk_index} of {filename} to {conn.getpeername()}")
                        else:
                            print(f"Chunk {chunk_index} not available in {filename}")
                else:
                    conn.sendall(f"{filename} not found on {self.peer_id}".encode('utf-8'))
                    
        except Exception as e:
            print(f"Error handling request: {e}")
            
        finally:
            conn.close()  # Đóng kết nối sau mỗi chunk yêu cầu

    def connect_to_tracker(self):
        self.tracker_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tracker_conn.connect((self.tracker_host, self.tracker_port))

    def register_file(self, filename, file_path):
        self.files[filename] = file_path
        self.connect_to_tracker()
        message = f"REGISTER {filename} {self.peer_id}:{self.peer_port}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        response = self.tracker_conn.recv(1024).decode('utf-8')
        print(response)
        self.tracker_conn.close()

    def request_file(self, filename):
        self.connect_to_tracker()
        message = f"REQUEST {filename}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        response = self.tracker_conn.recv(1024).decode('utf-8')
        print(response)
        self.tracker_conn.close()
        
        if "Peers for" in response and ":" in response:
            peer_info = response.split(':', 1)[-1].strip()
            peer_list = peer_info.strip("[]").split(", ")

            chunks = {}  # Lưu trạng thái tải của từng chunk
            for peer_address in peer_list:
                peer_address = peer_address.strip("[]' ")
                if ":" in peer_address:
                    host, port_str = peer_address.split(":")
                    try:
                        port = int(port_str)
                        peer_conn = self.download_file(filename, host, port, chunks)
                        if all(chunks.values()):
                            break
                    except ValueError:
                        print(f"Error: Invalid port '{port_str}' for peer '{host}'")
                else:
                    print(f"Error: Peer address '{peer_address}' is not valid.")
        else:
            print("Tracker response is not in expected format.")
    def save_file_from_chunks(self, filename, chunks):
        # Sắp xếp các chunks theo thứ tự để lưu chính xác
        with open(filename, 'wb') as f:
            for i in sorted(chunks.keys()):
                f.write(chunks[i])
        print(f"File `{filename}` đã được tải xong từ các chunks.")

def download_file(self, filename, host, port, chunks):
    chunk_index = 0
    while True:
        try:
            # Tạo một kết nối mới cho mỗi chunk
            peer_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_conn.connect((host, port))

            # Gửi yêu cầu tải chunk cụ thể
            peer_conn.sendall(f"GET {filename} {chunk_index}".encode('utf-8'))
            chunk = peer_conn.recv(4096)
            
            # Kiểm tra xem chunk có nhận được không
            if not chunk:
                print(f"Chunk {chunk_index} not available from {host}:{port}")
                break
            
            # Lưu chunk vào dictionary chunks
            chunks[chunk_index] = chunk
            print(f"Downloaded chunk {chunk_index} from {host}:{port}")

            # Tăng chỉ số chunk
            chunk_index += 1

        except ConnectionResetError:
            print(f"Connection reset by peer {host}:{port} while downloading chunk {chunk_index}")
            # Thử lại hoặc chuyển sang peer khác nếu cần
            break
        
        finally:
            # Đảm bảo đóng kết nối sau khi tải xong chunk
            peer_conn.close()

    # Sau khi hoàn thành việc tải tất cả các chunks, lưu file lại từ các chunks đã tải
    self.save_file_from_chunks(filename, chunks)

def split_file_into_chunks(file_path, chunk_size=4096):
    chunks = []
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
    return chunks
# Sử dụng peer
if __name__ == "__main__":

    peer1 = Peer("peer1")
    peer1.register_file("file1.txt", "file1.txt")
    chunks = split_file_into_chunks("file1.txt")
    print(f"File `file1.txt` được chia thành {len(chunks)} chunks.")
