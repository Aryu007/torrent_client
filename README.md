# Torrent File Downloader 🎯

This project is a simplified **Torrent File Downloader** that demonstrates how `.torrent` files are parsed and how peer-to-peer file pieces are downloaded using the BitTorrent protocol.

## 🚀 Features

- 🧲 Parse `.torrent` files to extract metadata
- 🧩 Connect to peers using tracker information
- 📥 Download file pieces from peers
- 🧮 Piece hashing to verify data integrity
- 📁 Save downloaded content to local storage

## 🛠️ Tech Stack

- **Language:** Python 
- **Protocol:** BitTorrent
- **Libraries Used:** 
  - Custom bencode parser
  - TCP socket programming
  - Multithreading 

## 🧪 How It Works

1. Load and parse the `.torrent` file.
2. Contact tracker to get list of peers.
3. Initiate connections with peers.
4. Request and receive file pieces.
5. Assemble and write the full file after all pieces are verified.