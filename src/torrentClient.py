import hashlib
import bencodepy
import logging
import os
from collections import OrderedDict
import random as rd

class torrent_metadata:
    def __init__(self, trackers_url_list, file_name, file_size, piece_length, pieces_count, pieces, info_hash, files):
        self.trackers_url_list  = trackers_url_list    
        self.file_name      = file_name                
        self.file_size      = file_size               
        self.piece_length   = piece_length
        self.pieces_count = pieces_count
        self.pieces         = pieces
        self.info_hash      = info_hash
        self.files          = files       
class torrent_file_reader(torrent_metadata):
    
    def __init__(self, file_name):
        full_torrent_file_path = os.path.join('../torrent', file_name + '.torrent')
        with open(full_torrent_file_path, 'rb') as file:
            torrent_data = file.read()
        self.torrent_file_raw_extract = bencodepy.decode(torrent_data)
        
        if b'encoding' in self.torrent_file_raw_extract.keys():
            self.encoding = self.torrent_file_raw_extract[b'encoding'].decode()
        else:
            self.encoding = 'UTF-8'
        ##################### 
        self.torrent_file_extract = self.extract_torrent_metadata(self.torrent_file_raw_extract)
        ##################### 

        if 'announce-list' in self.torrent_file_extract.keys():
            trackers_url_list = self.torrent_file_extract['announce-list'] 
        else:
            trackers_url_list = [self.torrent_file_extract['announce']]
        file_name    = self.torrent_file_extract['info'][b'name'].decode(self.encoding)
        piece_length = self.torrent_file_extract['info'][b'piece length']
        pieces       = self.split_piece_hash(self.torrent_file_extract['info'][b'pieces'])
        pieces_count = len(pieces)
        info_hash    = generate_info_hash(self.torrent_file_extract['info'])
        files = None
        if b'files' in self.torrent_file_extract['info'].keys():
            files_dictionary = self.torrent_file_extract['info'][b'files']
            files = [(file_data[b'length'], file_data[b'path']) for file_data in files_dictionary]
            file_size = 0
            for file_length in files:
                file_size += file_length[0]
        else: 
            file_size = self.torrent_file_extract['info'][b'length']
        super().__init__(trackers_url_list, file_name, file_size, piece_length, pieces_count, pieces, info_hash, files)
            

    def split_piece_hash(self, piece_hash):
        return [piece_hash[i:i+20] for i in range(0, len(piece_hash), 20)]
    def extract_torrent_metadata(self, torrent_file_raw_extract):
        torrent_extract = OrderedDict()
        for key, value in torrent_file_raw_extract.items():
            new_key = key.decode(self.encoding)
            if type(value) == OrderedDict:
                torrent_extract[new_key] = self.extract_torrent_metadata(value)
            elif type(value) == list and new_key == 'files':
                torrent_extract[new_key] = list(map(lambda x : self.extract_torrent_metadata(x), value))
            elif type(value) == list and new_key == 'path':
                torrent_extract[new_key] = value[0].decode(self.encoding)
            elif type(value) == list and new_key == 'url-list' or new_key == 'collections':
                torrent_extract[new_key] = list(map(lambda x : x.decode(self.encoding), value))
            elif type(value) == list :
                try:
                    torrent_extract[new_key] = list(map(lambda x : x[0].decode(self.encoding), value))
                except:
                    torrent_extract[new_key] = value
            elif type(value) == bytes and new_key != 'pieces':
                try:
                    torrent_extract[new_key] = value.decode(self.encoding)
                except:
                    torrent_extract[new_key] = value
            else :
                torrent_extract[new_key] = value
        return torrent_extract

    def get_data(self):
        return torrent_metadata(self.trackers_url_list, self.file_name, 
                                self.file_size,         self.piece_length, self.pieces_count,     
                                self.pieces,            self.info_hash, self.files)
   
    def __str__(self) -> str:
        units = ["Bytes", "KB", "MB", "GB"]
        
        def format_size(size):
            unit_index = 0
            while size >= 1024 and unit_index < len(units) - 1:
                size /= 1024
                unit_index += 1
            return round(size, 2), units[unit_index]
        
        size, size_unit = format_size(self.file_size)
        piece_length, piece_length_unit = format_size(self.piece_length)
        
        torrent_data = "CLIENT TORRENT DATA\n"
        torrent_data += f"File name: {self.file_name}\n"
        torrent_data += f"File size: {size} {size_unit}\n"
        torrent_data += f"Piece length: {piece_length} {piece_length_unit}\n"
        torrent_data += f"Info hash: {self.info_hash}\n"
        torrent_data += f"Files: {len(self.files) if self.files else self.files}\n"
        return torrent_data

class torrent_file_creater(torrent_metadata):
    def __init__(self, full_file_path: str):
        self.trackers_url_list = ['udp://tracker.example.com:6969']
        self.full_file_path = full_file_path
        self.file_name = os.path.basename(full_file_path)
        self.file_size = os.path.getsize(full_file_path)
        self.piece_length = 4096

        self.pieces = self.create_pieces_list(full_file_path)
        self.pieces_count = len(self.pieces)

        self.files = [(self.file_size, [self.file_name])]
        
        info_dict = {
            "length": self.file_size,
            "name": self.file_name.encode('utf-8'),
            "piece length": self.piece_length,
            "pieces": b"".join(self.pieces),
        }
        self.torrent_file_path = self.create_torrent_file()

        self.info_hash = generate_info_hash(info_dict)
        super().__init__(self.trackers_url_list, self.file_name, self.file_size, self.piece_length, self.pieces_count, self.pieces, self.info_hash, self.files)

    def create_pieces_list(self, full_file_path: str):
        pieces_list = []
        piece_size = self.piece_length
        with open(full_file_path, 'rb') as file:
            piece_index = 0
            while True:
                piece_data = file.read(piece_size)
                if not piece_data:
                    break
                pieces_list.append(self.calculate_piece_hash(piece_data))
                piece_index += 1
        return pieces_list

    def calculate_piece_hash(self, piece_data: bytes) -> bytes:
        sha1 = hashlib.sha1()
        sha1.update(piece_data)
        return sha1.digest()

    def create_torrent_file(self) -> str:
        metadata = {
            "announce": self.trackers_url_list[0],
            "announce-list": [self.trackers_url_list],
            "info": {
                "length": self.file_size,
                "name": self.file_name.encode('utf-8'),
                "piece length": self.piece_length,
                "pieces": b"".join(self.pieces),
            }
        }

        encoded_metadata = bencodepy.encode(metadata)

        torrent_dir_path = os.path.join('../torrent')
        if not os.path.exists(torrent_dir_path):
            os.makedirs(torrent_dir_path)

        torrent_path = os.path.join(torrent_dir_path, self.file_name + '.torrent')
        with open(torrent_path, "wb") as f:
            f.write(encoded_metadata)

        print(f"New .torrent file created: {torrent_path}")
        return torrent_path

def generate_info_hash(info_dict: dict) -> str:
    sha1_hash = hashlib.sha1()
    sha1_hash.update(bencodepy.encode(info_dict))
    return sha1_hash.digest().hex()
