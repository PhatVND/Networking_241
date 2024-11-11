# Peer-to-Peer File Sharing System

This project implements a basic peer-to-peer (P2P) file-sharing system with a tracker and multiple peers that can publish and download files.

## Files

1. **`tracker.py`**: The tracker that coordinates file sharing among peers.
2. **`peer.py`**: The peer that can register files to the tracker and download files from other peers.

## How to Run the Code

### 1. Start the Tracker (`tracker.py`)

To start the tracker, follow these steps:

- Open a terminal window.
- Navigate to the directory where `tracker.py` is located.
- Run the tracker by executing the following command:

```bash
python tracker.py
```
This will start the tracker on localhost and it will listen on port 5000 for peer requests.
## Publish a File (on Peer)
- Open a terminal, run:
```bash
python peer.py
```
- Enter username, then choose:    1 or publish → Enter filename and file path. Example:
```bash
1
file.txt
./peer1
```
## Download a File (on Another Peer)
- Open a terminal, run:
```bash
python peer.py
```
- Enter username, then choose:    2 or publish or download → Enter filename and download path. Example:
```bash
2
file.txt
./bokunopico/theplace_ilive
```
## Exit the Program
- Type 3 or exit to exit.
