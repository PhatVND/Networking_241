import socket
import threading
import os

class Peer:
    def __init__(self, peer_id, tracker_host='127.0.0.1', tracker_port=5000):
        self.peer_id = peer_id
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.files = {}  # Lưu các file mà peer này có dưới dạng {'filename': 'file_path'}
        
        # Tạo socket với cổng ngẫu nhiên để lắng nghe
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('localhost', 0))  # 0 để hệ điều hành tự chọn cổng ngẫu nhiên
        self.server_socket.listen()
        self.peer_host, self.peer_port = self.server_socket.getsockname()  # Lấy cổng đã gán ngẫu nhiên
        print(f"{self.peer_id} is listening on port {self.peer_port}")
        
        # Bắt đầu luồng lắng nghe để peer có thể chia sẻ file khi có yêu cầu
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
                filename = params[0]
                if filename in self.files:
                    with open(self.files[filename], 'rb') as f:  # Đọc file ở chế độ nhị phân
                        while chunk := f.read(4096):  # Đọc và gửi từng khối dữ liệu
                            conn.sendall(chunk)
                    print(f"Sent {filename} to {conn.getpeername()}")
                else:
                    conn.sendall(f"{filename} not found on {self.peer_id}".encode('utf-8'))
        
        finally:
            conn.close()

    def connect_to_tracker(self):
        self.tracker_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tracker_conn.connect((self.tracker_host, self.tracker_port))

    def register_file(self, filename, file_path):
        # Đăng ký file này với tracker
        self.files[filename] = file_path
        self.connect_to_tracker()
        message = f"REGISTER {filename} {self.peer_id}:{self.peer_port}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        response = self.tracker_conn.recv(1024).decode('utf-8')
        print(response)
        self.tracker_conn.close()

    def request_file(self, filename):
        # Gửi yêu cầu tới tracker để tìm peer có file này
        self.connect_to_tracker()
        message = f"REQUEST {filename}"
        self.tracker_conn.sendall(message.encode('utf-8'))
        response = self.tracker_conn.recv(1024).decode('utf-8')
        print(response)
        self.tracker_conn.close()
        
        # Parse danh sách các peer từ phản hồi của tracker
        if "Peers for" in response and ":" in response:
            peer_info = response.split(':', 1)[-1].strip()
            peer_list = peer_info.strip("[]").split(", ")

            for peer_address in peer_list:
                peer_address = peer_address.strip("[]' ")  # Loại bỏ các ký tự không cần thiết
                if ":" in peer_address:
                    host, port_str = peer_address.split(":")
                    try:
                        port = int(port_str)  # Kiểm tra cổng là số hợp lệ
                        self.download_file(filename, host, port)
                        break  # Tải từ peer đầu tiên có file
                    except ValueError:
                        print(f"Error: Invalid port '{port_str}' for peer '{host}'")
                else:
                    print(f"Error: Peer address '{peer_address}' is not valid.")
        else:
            print("Tracker response is not in expected format.")

    def download_file(self, filename, host, port):
        peer_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_conn.connect((host, port))
        peer_conn.sendall(f"GET {filename}".encode('utf-8'))
        
        # Nhận và lưu toàn bộ nội dung file
        file_content = b""  # Khởi tạo với kiểu byte
        while True:
            data = peer_conn.recv(4096)
            if not data:  # Khi không còn dữ liệu để nhận
                break
            file_content += data
        
        # Ghi nội dung vào file ở chế độ nhị phân
        with open(filename, 'wb') as f:
            f.write(file_content)
        
        print(f"{self.peer_id} downloaded {filename} from {host}:{port}")
        peer_conn.close()

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

    peer2 = Peer("peer2")
    peer2.register_file("file2.txt", "file2.txt")
