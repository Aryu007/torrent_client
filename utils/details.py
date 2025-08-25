# Importing utility functions from the 'utils/get_details' module
from utils.get_details import *

# -------------------------------
# Class: TorrentDetails
# -------------------------------
# This class is used to store and organize all the necessary details
# about a torrent file such as piece length, total size, number of pieces,
# piece hashes, file paths, etc.

class TorrentDetails:
    def __init__(self, info_dict: dict, root: str):
        """
        Initializes the TorrentDetails object with extracted metadata.

        Args:
            info_dict (dict): Parsed information from the torrent's "info" dictionary.
            root (str): Root directory path where the files will be downloaded.
        """
        # Size of each piece in bytes
        self.piece_length = get_piece_length(info_dict)

        # Total size of the torrent (sum of all files)
        self.total_length = get_total_length(info_dict)

        # Total number of pieces in the torrent
        self.num_of_pieces = get_total_pieces(self.total_length, self.piece_length)

        # List of file sizes (for multi-file torrents)
        self.file_sizes = get_file_sizes(info_dict)

        # List of SHA1 hashes for each piece
        self.hash_of_pieces = get_hash_list(info_dict, self.num_of_pieces)

        # Unique SHA1 hash (info hash) used to identify the torrent
        self.info_hash = get_info_hash(info_dict)

        # Details of the files to be downloaded, including paths and sizes
        self.files = get_file_details(info_dict, root)


# -------------------------------
# Class: ParsedMessage
# -------------------------------
# Represents a parsed message from a peer connection.
# Each message typically contains:
# - size: length of the message
# - id: identifier indicating message type
# - payload: the actual data in the message
class ParsedMessage:
    def __init__(self, size, id, payload):
        """
        Initializes a ParsedMessage instance.

        Args:
            size (int): Size of the message in bytes.
            id (int): ID representing the type of message.
            payload (bytes): Actual payload of the message.
        """
        self.size = size
        self.id = id
        self.payload = payload


# -------------------------------
# Class: Peer
# -------------------------------
# Represents a peer (another user/node in the torrent network) with an IP and Port.
class Peer:
    def __init__(self, ip: str, port: int):
        """
        Initializes a Peer object.

        Args:
            ip (str): IP address of the peer.
            port (int): Port number on which the peer is listening.
        """
        self.ip = ip
        self.port = port

    def __str__(self):
        """
        Returns a readable string representation of the Peer.
        Example: '192.168.1.10:6881'
        """
        return f"{self.ip}:{self.port}"
