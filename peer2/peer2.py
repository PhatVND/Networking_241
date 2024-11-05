import socket
import threading
import os

class Peer:
    def __init__(self, peer_id, tracker_host='127.0.0.1', tracker_port=5000):
        self.peer_id = peer_id
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.files = {}
        self.total_chunks = 0  # Số chunk của file hiện tại mà peer đang giữ

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
        # Tính tổng số chunks của file
        self.total_chunks = self.calculate_total_chunks(file_path)
        self.connect_to_tracker()
        # Gửi lệnh `REGISTER` cùng với tổng số chunk
        message = f"REGISTER {filename} {self.total_chunks} {self.peer_id}:{self.peer_port}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        response = self.tracker_conn.recv(1024).decode('utf-8')
        print(response)
        self.tracker_conn.close()

    def calculate_total_chunks(self, file_path, chunk_size=4096):
        # Đếm tổng số chunks dựa trên kích thước file
        file_size = os.path.getsize(file_path)
        return (file_size + chunk_size - 1) // chunk_size  # Làm tròn lên
    
    def save_file_from_chunks(self, filename, chunks):
        # Sắp xếp các chunks theo thứ tự để lưu chính xác
        with open(filename, 'wb') as f:
            for i in sorted(chunks.keys()):
                f.write(chunks[i])
        print(f"File `{filename}` đã được tải xong từ các chunks.")
        self.register_file(filename, filename)

    def request_file(self, filename):
        # Yêu cầu danh sách các peers từ tracker
        self.connect_to_tracker()
        message = f"REQUEST {filename}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        response = self.tracker_conn.recv(1024).decode('utf-8')
        print(response)
        self.tracker_conn.close()

        # Phân tích danh sách các peers
        if "Peers for" in response and ":" in response:
            peer_info = response.split(':', 1)[-1].strip()
            peer_list = peer_info.strip("[]").split(", ")

            # Gán peer1 và peer2
            if len(peer_list) >= 2:
                peer1_address = peer_list[0].strip("[]' ")
                peer2_address = peer_list[1].strip("[]' ")

                # Tách host và port
                host1, port_str1 = peer1_address.split(":")
                host2, port_str2 = peer2_address.split(":")
                port1, port2 = int(port_str1), int(port_str2)

                chunks = {}
                # Yêu cầu từng chunk từ peer1 và peer2
                for chunk_index in range(self.total_chunks):  # Sử dụng `self.total_chunks` cho file hiện tại
                    if chunk_index % 2 == 0:
                        # Chunks chẵn từ peer2
                        chunk = self.download_chunk_from_peer(filename, host2, port2, chunk_index)
                    else:
                        # Chunks lẻ từ peer1
                        chunk = self.download_chunk_from_peer(filename, host1, port1, chunk_index)
                    
                    if chunk:
                        chunks[chunk_index] = chunk
                    else:
                        print(f"Failed to download chunk {chunk_index}")
                
                # Lưu file từ các chunks đã tải
                self.save_file_from_chunks(filename, chunks)
        else:
            print("Tracker response is not in expected format.")

    def download_chunk_from_peer(self, filename, host, port, chunk_index):
        peer_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_conn.connect(('localhost', port))
        # Gửi yêu cầu với số chunk cụ thể
        peer_conn.sendall(f"GET {filename} {chunk_index}".encode('utf-8'))
        
        # Nhận dữ liệu chunk
        chunk = peer_conn.recv(4096)
        print(f"Downloaded chunk {chunk_index} from {host}:{port}")
        peer_conn.close()
        return chunk

def split_file_into_chunks(file_path, chunk_size=4096):
    chunks = []
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunks.append(chunk)
    return chunks

if __name__ == "__main__":
    peer2 = Peer("peer2")
    peer2.register_file("file1.txt", "file1.txt")
    chunks = split_file_into_chunks("file1.txt")
    print(f"File `file1.txt` được chia thành {len(chunks)} chunks.")
