# Peer-to-Peer File Sharing System

This project implements a basic peer-to-peer (P2P) file-sharing system with a tracker and multiple peers that can publish and download files.

## Files

1. **`peer.py`**: The peer that can register files to the tracker and download files from other peers.
2. **`torrentClient.py`**: The peer that can register files to the tracker and download files from other peers.
3. **`tracker.py`**: The tracker that coordinates file sharing among peers.
4. **`database.py`**: The peer that can register files to the tracker and download files from other peers.
5. **`queries.sql`**: Tracker used to create table.


## How to Run the Code

### Connect database
Install database postgresql and GUI like SQLTools with its driver.
Install some package like psycopg2, bencodepy

### 1. Start the Tracker (`tracker.py`)

To start the tracker, follow these steps:

- Open a terminal window.
- Navigate to the directory where `tracker.py` is located.
- Run the tracker by executing the following command:

```bash
python tracker.py
```
This will start the tracker on localhost and it will listen on port 5000 for peer requests.

## 2. Create Torrent (on Peer)
- Open a terminal, run:
```bash
python peer.py
```
- Enter username, then choose:    1 or torrent → Enter filename and file path. Example:
```bash
1
file.txt
./peer1
```
## 3. Seeding a File (on Peer)
- Open a terminal, run:
```bash
python peer.py
```
- Enter username, then choose:    2 or seeding → Enter filename and file path. Example:
```bash
2
file.txt
./peer1
```
## 4. Download a File (on Another Peer)
- Open a terminal, run:
```bash
python peer.py
```
- Enter username, then choose:    3 or download → Enter filename and download path. Example:
```bash
3
file.txt
./peer2
```
## Exit the Program
- Crtl + C 
## Supervisor Database
- Go to database to watch change when register, when a peer disconnect or tracker disconnect