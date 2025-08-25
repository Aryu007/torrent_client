# -------------------------------
# Handlers and Hash Verification
# -------------------------------
# This module provides:
# 1. Handlers for 'have' and 'bitfield' messages in the BitTorrent protocol
# 2. Function to verify piece integrity using SHA-1 hashing

from utils.details import *
from typing import List
import struct
import hashlib

def have_handler(parsed_message: ParsedMessage, verified_pieces: List[bool]) -> List[int]:
    """
    Handles a 'have' message to update the state of available pieces.

    Args:
        parsed_message (ParsedMessage): The parsed message containing the piece index.
        verified_pieces (List[bool]): A list indicating which pieces are already verified.

    Returns:
        List[int]: List of piece indices that are newly available.
    """
    piece_index, = struct.unpack(">I", parsed_message.payload)  # Big-endian unsigned int
    result = []

    if not verified_pieces[piece_index]:
        result.append(piece_index)

    return result

def bitfield_handler(parsed_message: ParsedMessage, verified_pieces: List[bool]) -> List[int]:
    """
    Handles a 'bitfield' message to get all the pieces a peer has.

    Args:
        parsed_message (ParsedMessage): The parsed message containing the bitfield payload.
        verified_pieces (List[bool]): A list indicating which pieces are already verified.

    Returns:
        List[int]: List of indices of pieces that the peer has but are not verified locally.
    """
    payload = parsed_message.payload
    total_pieces = len(verified_pieces)
    result = []

    for byte_index, byte in enumerate(payload):
        for bit in range(8):
            piece_index = byte_index * 8 + (7 - bit)
            if piece_index >= total_pieces:
                break
            has_piece = (byte >> bit) & 1
            if has_piece and not verified_pieces[piece_index]:
                result.append(piece_index)

    return result

def verify_piece_hash(piece_data: bytearray, piece_hash: bytes) -> bool:
    """
    Verifies the SHA-1 hash of a downloaded piece.

    Args:
        piece_data (bytearray): The data of the downloaded piece.
        piece_hash (bytes): The expected SHA-1 hash of the piece.

    Returns:
        bool: True if the piece hash matches, False otherwise.
    """
    calculated_hash = hashlib.sha1(piece_data).digest()
    return calculated_hash == piece_hash
