CREATE TABLE IF NOT EXISTS peers (
    peer_ip VARCHAR(20) PRIMARY KEY,
    uploaded BIGINT,
    downloaded BIGINT,
    left_bytes BIGINT
);
CREATE TABLE IF NOT EXISTS piece_peers (
    info_hash VARCHAR(40),
    piece_index INT,
    peer_ip VARCHAR(20),
    PRIMARY KEY (info_hash, piece_index, peer_ip),
    FOREIGN KEY (peer_ip) REFERENCES peers(peer_ip) ON DELETE CASCADE
);
