import struct
import random
import socket
import asyncio
import utils.details as details
from utils.details import TorrentDetails, ParsedMessage
import utils.handlers as handler

# -------------------------------
# Function: build_bitTorrent_handshake
# -------------------------------
def build_bitTorrent_handshake(details: TorrentDetails):
    """
    Builds the handshake message for the BitTorrent protocol.

    Args:
        details (TorrentDetails): Object containing torrent metadata.

    Returns:
        bytes: Packed handshake request to send to peers.
    """
    pstrlen = 19  # Protocol string length
    pstr = b"BitTorrent protocol"
    # Generate a random peer_id (mimicking a standard BitTorrent client)
    peer_id = b'-TR4003-' + bytes(random.getrandbits(8) for _ in range(12))
    # Pack the handshake request according to the BitTorrent spec
    handshake_req = struct.pack(">B19s8x20s20s", pstrlen, pstr, details.info_hash, peer_id)
    return handshake_req


# -------------------------------
# Keep-Alive and State Messages
# -------------------------------
def build_keep_alive():
    """Build a keep-alive message (used to keep peer connections open)."""
    return struct.pack(">I", 0)

def build_choke():
    """Build a choke message (indicates the peer will not send pieces)."""
    return struct.pack(">Ib", 1, 0)

def build_unchoke():
    """Build an unchoke message (indicates the peer can send pieces)."""
    return struct.pack(">Ib", 1, 1)

def build_interested():
    """Build an interested message (requesting pieces from the peer)."""
    return struct.pack(">Ib", 1, 2)

def build_uninterested():
    """Build an uninterested message (no longer requesting pieces)."""
    return struct.pack(">Ib", 1, 3)


# -------------------------------
# Have & Bitfield Messages
# -------------------------------
def build_have(piece_index: int):
    """
    Build a 'have' message indicating possession of a piece.

    Args:
        piece_index (int): Index of the piece that has been downloaded.
    """
    return struct.pack(">IbI", 5, 4, piece_index)

def build_bitfeild(bitfeild: list, details: TorrentDetails):
    """
    Build a bitfield message indicating which pieces are already downloaded.

    Args:
        bitfeild (list): Boolean list representing possession of pieces.
        details (TorrentDetails): Torrent metadata.

    Returns:
        bytes: Packed bitfield message.
    """
    bitfield_length = (details.num_of_pieces + 7) // 8
    bitfield_bytes = bytearray(bitfield_length)

    # Set bits for pieces we have
    for i, has_piece in enumerate(bitfeild):
        if has_piece:
            bitfield_bytes[i // 8] |= (1 << (7 - (i % 8)))

    total_length = 1 + len(bitfield_bytes)
    return struct.pack(">Ib", total_length, 5) + bytes(bitfield_bytes)


# -------------------------------
# Piece Request/Response Messages
# -------------------------------
def build_request(piece_index: int, begin: int, length: int):
    """
    Build a request message to download a block of a piece.

    Args:
        piece_index (int): Index of the piece.
        begin (int): Offset within the piece.
        length (int): Length of the block to download.
    """
    return struct.pack(">IbIII", 13, 6, piece_index, begin, length)

def build_piece(piece_index: int, begin: int, block: bytes):
    """
    Build a piece message to send a data block.

    Args:
        piece_index (int): Index of the piece.
        begin (int): Offset within the piece.
        block (bytes): Data block content.
    """
    block_length = len(block)
    total_length = 9 + block_length
    header = struct.pack(">IbII", total_length, 7, piece_index, begin)
    return header + block

def build_cancel(piece_index: int, begin: int, length: int):
    """
    Build a cancel message to stop requesting a specific block.

    Args:
        piece_index (int): Index of the piece.
        begin (int): Offset within the piece.
        length (int): Length of the block.
    """
    return struct.pack(">IbIII", 13, 8, piece_index, begin, length)


# -------------------------------
# Port Message
# -------------------------------
def build_port(port: int):
    """
    Build a port message to indicate a listening port for DHT.

    Args:
        port (int): The port number.
    """
    return struct.pack(">IbH", 3, 9, port)


# -------------------------------
# Data Reception Utilities
# -------------------------------
def recvall(sock: socket.socket, n: int) -> bytes:
    """
    Read exactly `n` bytes from a socket.

    Args:
        sock (socket.socket): The socket object.
        n (int): Number of bytes to read.

    Returns:
        bytes: Data read from the socket.

    Raises:
        ConnectionError: If the peer closes the connection.
    """
    data = b''
    while len(data) < n:
        part = sock.recv(n - len(data))
        if not part:
            raise ConnectionError("Peer closed connection")
        data += part
    return data

async def recv_whole_message(reader: asyncio.StreamReader, isHandshake: bool) -> bytes:
    """
    Read an entire message from the peer, handling both handshake and normal messages.

    Args:
        reader (asyncio.StreamReader): Async IO reader for the connection.
        isHandshake (bool): Whether this is a handshake message.

    Returns:
        bytes: The full message payload.
    """
    if isHandshake:
        # Handshake messages are fixed length (68 bytes)
        message = await reader.readexactly(68)
    else:
        # Normal messages: first read length prefix, then payload
        len_bytes = await reader.readexactly(4)
        length = struct.unpack(">I", len_bytes)[0]
        payload = await reader.readexactly(length)
        message = len_bytes + payload
    return message


# -------------------------------
# Message Parsing
# -------------------------------
def parse_message(packet: bytes) -> ParsedMessage:
    """
    Parse a raw packet into a structured ParsedMessage object.

    Args:
        packet (bytes): The raw message packet from the peer.

    Returns:
        ParsedMessage: Structured message with length, ID, and payload.
    """
    length = None if len(packet) < 4 else struct.unpack(">I", packet[:4])[0]
    id = None if len(packet) < 5 else struct.unpack(">b", packet[4:5])[0]
    payload = None if len(packet) < 6 else packet[5:]
    return ParsedMessage(length, id, payload)
