import psycopg2
import logging
import os
from psycopg2 import sql

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

def connect_to_database():
    try:
        connection = psycopg2.connect(
            dbname="postgres", 
            user="postgres",
            password="12345678",
            host="localhost",
            port="5432"
        )
        return connection
    except Exception as e:
        logging.error(f"Error connecting to database: {e}")
        return None

def execute_sql_query(query, params=None):
    try:
        connection = connect_to_database()
        cursor = connection.cursor()
        cursor.execute(query, params)
        if(cursor.description) is not None:
            return cursor.fetchall()

        connection.commit()
        
        return True
    except Exception as e:
        logging.error(f"Error executing query: {e}")
        connection.rollback()
        return False
    finally:
        cursor.close()
        connection.close()

def execute_sql_from_file(file_path):
    try:
        with open(file_path, 'r') as file:
            sql_queries = file.read()
        
        queries = sql_queries.split(';')
        for query in queries:
            if query.strip():
                execute_sql_query(query)
    except Exception as e:
        logging.error(f"Error executing SQL from file {file_path}: {e}")

def register_peer_in_database(peer_ip):
    query = """
        INSERT INTO peers (peer_ip, uploaded, downloaded, left_bytes)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (peer_ip) DO UPDATE
        SET uploaded = EXCLUDED.uploaded,
            downloaded = EXCLUDED.downloaded,
            left_bytes = EXCLUDED.left_bytes
        """
    uploaded = 0
    downloaded = 0
    left_bytes = 0
    # status = 0
    # last_update = 0
    # connection_time = 0
    params = (peer_ip, uploaded, downloaded, left_bytes)
    try:
        is_query_executed = execute_sql_query(query, params)
        if not is_query_executed:
            return False
        return True
    except Exception as e:
        logging.error(f"Error registering peer {peer_ip}: {e}")
        return False

def register_piece_in_database(info_hash, pieces_list, peer_ip):
    peer_registered = register_peer_in_database(peer_ip)
    if not peer_registered:
        logging.error(f"Peer {peer_ip} registration failed. Aborting piece registration.")
        return False
    
    query = """
        INSERT INTO piece_peers (info_hash, piece_index, peer_ip)
        VALUES (%s, %s, %s)
        ON CONFLICT (info_hash, piece_index, peer_ip) DO NOTHING;
    """
    params = [(info_hash, piece_index, peer_ip) for piece_index in pieces_list]
    try:
        for param in params:
            execute_sql_query(query, param)
        logging.debug(f"Peer {peer_ip} seeding PIECE for torrent {info_hash}.")
        return True
    except Exception as e:
        logging.error(f"Error registering pieces for peer {peer_ip}: {e}")
        return False
    
def get_peers_list_seeding_file_from_database(torrent_hash):
    query = """
        SELECT DISTINCT peer_ip
        FROM piece_peers
        WHERE info_hash = %s;
        """
    params = (torrent_hash,)
    try:
        result = execute_sql_query(query, params)
        peer_ips = [row[0] for row in result]
        
        return peer_ips
    except Exception as e:
        logging.error(f"Error getting peers seeding file {torrent_hash}: {e}")
        return None

def delete_piece_peers_from_database(peer_ip):
    query = """
        DELETE FROM piece_peers
        WHERE peer_ip = %s;
    """
    params = (peer_ip,)
    try:
        execute_sql_query(query, params)
        logging.info(f"PIECE_PEERS for peer {peer_ip} deleted successfully.")
        return True
    except Exception as e:
        logging.error(f"Error deleting peer {peer_ip}: {e}")
        return False
    
def delete_peer_from_database(peer_ip):
    delete_piece_peers_from_database(peer_ip)
    query = """
        DELETE FROM peers
        WHERE peer_ip = %s;
    """
    params = (peer_ip,)
    try:
        execute_sql_query(query, params)
        logging.info(f"PEER {peer_ip} deleted successfully.")
        return True
    except Exception as e:
        logging.error(f"Error deleting peer {peer_ip}: {e}")
        return False

def drop_tables_from_database():
    query = """
        DROP TABLE IF EXISTS piece_peers;
        DROP TABLE IF EXISTS peers;
    """
    try:
        execute_sql_query(query)
        logging.info("TABLE dropped successfully.")
        return True
    except Exception as e:
        logging.error(f"Error dropping tables: {e}")
        return False