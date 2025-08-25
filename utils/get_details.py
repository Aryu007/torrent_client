import sys
from math import ceil
from typing import List
import bencodepy
import hashlib

# -------------------------------
# Function: get_piece_length
# -------------------------------
# Extracts the piece length (in bytes) from the torrent info dictionary.
def get_piece_length(info_dict: dict) -> int:
    """
    Get the size of each piece in the torrent.

    Args:
        info_dict (dict): The "info" section of the torrent metadata.

    Returns:
        int: Piece length in bytes.
    """
    try:
        length = info_dict[b'piece length']
    except Exception as E:
        print(f"Error: {E}")
        sys.exit(1)

    return length


# -------------------------------
# Function: get_total_length
# -------------------------------
# Calculates the total size of the torrent (for single or multi-file torrents).
def get_total_length(info_dict: dict) -> int:
    """
    Calculate the total size of all files in the torrent.

    Args:
        info_dict (dict): The "info" section of the torrent metadata.

    Returns:
        int: Total size of all files in bytes.
    """
    total_length = 0
    try:
        # Multi-file torrent
        if b'files' in info_dict:
            for file in info_dict[b'files']:
                total_length += file[b'length']
        # Single-file torrent
        else:
            total_length += info_dict[b'length']

    except Exception as E:
        print(f"Error: {E}")
        sys.exit(1)

    return total_length


# -------------------------------
# Function: get_total_pieces
# -------------------------------
# Determines how many pieces the torrent is split into.
def get_total_pieces(total_length: int, piece_length: int) -> int:
    """
    Calculate the total number of pieces required.

    Args:
        total_length (int): Total size of the torrent in bytes.
        piece_length (int): Size of each piece in bytes.

    Returns:
        int: Total number of pieces.
    """
    return ceil(total_length / piece_length)


# -------------------------------
# Function: get_file_sizes
# -------------------------------
# Returns a list containing sizes of individual files in the torrent.
def get_file_sizes(info_dict: dict) -> list:
    """
    Extract sizes of individual files in the torrent.

    Args:
        info_dict (dict): The "info" section of the torrent metadata.

    Returns:
        list: Sizes of all files in bytes.
    """
    file_sizes = []
    try:
        # Multi-file torrent
        if b'files' in info_dict:
            for file in info_dict[b'files']:
                file_sizes.append(file[b'length'])
        # Single-file torrent
        else:
            file_sizes.append(info_dict[b'length'])

    except Exception as E:
        print(f"Error: {E}")
        sys.exit(1)

    return file_sizes


# -------------------------------
# Function: get_hash_list
# -------------------------------
# Splits the concatenated SHA1 hashes of each piece into a list.
def get_hash_list(info_dict: dict, num_of_pieces: int) -> List[bytes]:
    """
    Extracts the SHA1 hash for each piece in the torrent.

    Args:
        info_dict (dict): The "info" section of the torrent metadata.
        num_of_pieces (int): Total number of pieces.

    Returns:
        List[bytes]: List of SHA1 hashes for each piece.
    """
    hashes = []
    pieces = info_dict[b'pieces']

    for i in range(num_of_pieces):
        # Each SHA1 hash is 20 bytes long
        hashes.append(pieces[20 * i:20 * (i + 1)])

    return hashes


# -------------------------------
# Function: get_info_hash
# -------------------------------
# Generates the unique info hash (SHA1) used for peer and tracker communication.
def get_info_hash(info_dict: dict) -> bytes:
    """
    Generate the SHA1 hash of the 'info' dictionary (info_hash).

    Args:
        info_dict (dict): The "info" section of the torrent metadata.

    Returns:
        bytes: SHA1 hash digest of the info dictionary.
    """
    # Bencode the info dict to generate consistent bytes for hashing
    info_bencoded = bencodepy.encode(info_dict)
    info_hash = hashlib.sha1(info_bencoded).digest()

    return info_hash


# -------------------------------
# Function: get_file_details
# -------------------------------
# Provides a structured list of file paths, lengths, and offsets.
def get_file_details(info_dict: dict, root: str):
    """
    Get detailed information of each file in the torrent.

    Args:
        info_dict (dict): The "info" section of the torrent metadata.
        root (str): Root path where the files will be saved.

    Returns:
        list: List of dictionaries containing:
            - path: File path where the file will be downloaded.
            - length: Size of the file in bytes.
            - offset: Offset position for the file in the concatenated data.
    """
    files_list = []

    # Multi-file torrent
    if b'files' in info_dict:
        offset = 0
        for file_info in info_dict[b'files']:
            # Convert byte strings to human-readable strings
            file_path_str = [s.decode('utf-8') for s in file_info[b'path']]
            file_path = '/'.join(file_path_str)
            file_length = file_info[b'length']

            files_list.append({
                'path': root + file_path,
                'length': file_length,
                'offset': offset,
            })

            # Update offset for the next file
            offset += file_length

    # Single-file torrent
    else:
        file_length = info_dict.get(b'length', 0)
        files_list.append({
            'path': root + info_dict.get(b'name', b'').decode('utf-8'),
            'length': file_length,
            'offset': 0,
        })

    return files_list


# -------------------------------
# Module Export
# -------------------------------
# Specifies the functions to be exported when this module is imported.
__all__ = [
    "get_piece_length",
    "get_total_length",
    "get_total_pieces",
    "get_file_sizes",
    "get_hash_list",
    "get_info_hash",
    "get_file_details"
]
