# ============================
# Distributed Torrent Client - Entry Point (master.py)
# ============================

import bencodepy      # For decoding and encoding .torrent files (bencoded format)
import sys            # For handling command-line arguments and system exits
import threading      # For running peer discovery and download in parallel threads
import queue          # For thread-safe peer queue management
import hashlib        # For generating SHA-1 hash of torrent info (info_hash)
import os             # For file and directory operations
import time           # For timestamps and delays
import asyncio        # For asynchronous peer communication

# Importing internal utility modules
from utils.get_peers import *       # Functions to query trackers and fetch peers
from utils.download import *        # Functions to manage downloading from peers
from utils.json_data import ResumeData  # Class to manage saving and loading resume state
from utils.details import TorrentDetails # Class to parse and manage torrent metadata
from utils.logger import Logger         # Logger for stats and progress updates

# Constant for resume file name used to store download progress
RESUME_FILENAME = "resume.json"

# Thread-safe queue to store peers fetched from tracker
peers_list = queue.Queue()

# Initialize logger and start displaying download stats in background
logger = Logger()
logger.display_stats_loop()

# ------------------------------------------
# Function: populate_peers
# Description:
#   Periodically contacts the tracker, retrieves a peer list,
#   and pushes peers into the shared queue for the downloader.
# ------------------------------------------
def populate_peers(torrent_info: dict, info_hash: bytes, logger: Logger):
    while True:
        # Fetch fresh peer list from the tracker and put into peers_list queue
        get_peers_list(torrent_info, info_hash, peers_list, logger)
        # Retrieve tracker interval and swarm stats (seeders/leechers)
        [Interval, Seeder, Leecher] = get_interval_data()
        print(f"Interval:{Interval}, Seeders:{Seeder}, Leechers:{Leecher}")
        # Sleep until next tracker interval
        time.sleep(Interval + 1)

# ------------------------------------------
# Function: connect_to_peers
# Description:
#   Consumes peers from the queue and starts asynchronous
#   connections to download pieces of the torrent.
# ------------------------------------------
def connect_to_peers(details: TorrentDetails, resume_data: ResumeData, logger: Logger):
    while True:
        # Get next peer from the queue
        peers = peers_list.get()
        # Asynchronously start the downloading process with selected peers
        asyncio.run(main(peers, details, resume_data, logger))

# ------------------------------------------
# Main Entry Point
# ------------------------------------------
if __name__ == "__main__":

    # Validate command-line arguments
    if len(sys.argv) != 3:
        print("Usage: python3 master.py <path_to_torrent_file> <path_to_download>")
        sys.exit(1)

    file_name = sys.argv[1]  # Path to .torrent file
    save_loc = sys.argv[2]   # Download directory

    # Step 1: Read the .torrent file
    try:
        with open(file_name, "rb") as torrent_file:
            file_content = torrent_file.read()
    except FileNotFoundError:
        print(f"Error: file {file_name} not found!")
        sys.exit(1)
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    # Step 2: Decode the torrent metadata using bencode
    try:
        torrent_info = bencodepy.decode(file_content)
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    # Step 3: Extract info dictionary and generate info_hash
    try:
        info_dict = torrent_info[b'info']
        info_bencoded = bencodepy.encode(info_dict)
        info_hash = hashlib.sha1(info_bencoded).digest()
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    # Step 4: Determine download directory based on torrent type (single file or multi-file)
    name = info_dict[b'name'].decode('utf-8')
    if b'files' in info_dict:
        dir_path = os.path.join(save_loc, name)
    else:
        root, ext = os.path.splitext(name)
        dir_path = os.path.join(save_loc, root)
    dir_path = dir_path + '/'

    # Create torrent details object
    details = TorrentDetails(info_dict, dir_path)

    # Step 5: Setup resume data and ensure download directory exists
    try:
        os.makedirs(dir_path, exist_ok=True)
        json_file_path = os.path.join(dir_path, RESUME_FILENAME)

        if RESUME_FILENAME in os.listdir(dir_path):
            # Load existing resume state to continue download
            resume_data = ResumeData.from_json(json_file_path)
        else:
            # Create a fresh resume state for a new download
            resume_data = ResumeData(
                info_hash=details.info_hash.hex(),
                piece_length=details.piece_length,
                total_pieces=details.num_of_pieces,
                downloaded=0,
                file_sizes=details.file_sizes,
                mtime=int(time.time()),
                verified_pieces=[False for _ in range(details.num_of_pieces)],
                last_active=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
    except Exception as E:
        print(f"Error : {type(E).__name__} {E}")
        sys.exit(1)

    # Step 6: Start tracker thread and peer connector thread
    try:
        # Thread for periodically populating peers from tracker
        tracker_thread = threading.Thread(target=populate_peers, args=(torrent_info, info_hash, logger))
        # Thread for connecting to peers and downloading
        connector_thread = threading.Thread(target=connect_to_peers, args=(details, resume_data, logger))

        tracker_thread.start()
        connector_thread.start()

        tracker_thread.join()
        connector_thread.join()

    # Step 7: Graceful shutdown on keyboard interrupt
    except KeyboardInterrupt:
        print("Exiting. Saving resume data.")
        resume_data.to_json(json_file_path)
        sys.exit(0)
