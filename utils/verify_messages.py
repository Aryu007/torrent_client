import struct
from utils.details import *

def is_handshake(packet: bytes, info_hash: bytes) -> bool:
    """
    Checks if the given packet is a valid BitTorrent handshake packet.

    Handshake packet structure:
    ----------------------------------------------------------------
    - 1 byte   : length of protocol string (should be 19)
    - 19 bytes : protocol string ("BitTorrent protocol")
    - 8 bytes  : reserved bytes (ignored here)
    - 20 bytes : info_hash (must match the torrent's info_hash)
    - 20 bytes : peer_id (identifier of the peer)
    ----------------------------------------------------------------

    Args:
        packet (bytes): Raw packet data (should be exactly 68 bytes long)
        info_hash (bytes): Expected info_hash of the torrent

    Returns:
        bool: True if the packet is a valid handshake, otherwise False
    """
    # A valid handshake packet must be exactly 68 bytes
    if len(packet) != 68:
        return False

    # Unpack the packet: 
    # >     : big-endian
    # B     : 1-byte length of protocol string
    # 19s   : 19-byte protocol string
    # 8x    : skip 8 reserved bytes
    # 20s   : 20-byte info_hash
    # 20s   : 20-byte peer_id
    len_resp, msg_resp, info_hash_resp, peer_id_resp = struct.unpack(">B19s8x20s20s", packet)

    # Validate the components of the handshake
    if len_resp != 19 or msg_resp != b'BitTorrent protocol' or info_hash_resp != info_hash:
        return False

    return True


def is_have(msg: ParsedMessage) -> bool:
    """
    Checks if the message is a 'have' message.
    ID = 4 (BitTorrent specification)
    """
    return msg.id == 4


def is_bitfeild(msg: ParsedMessage) -> bool:
    """
    Checks if the message is a 'bitfield' message.
    ID = 5 (BitTorrent specification)
    """
    return msg.id == 5


def is_choke(msg: ParsedMessage) -> bool:
    """
    Checks if the message is a 'choke' message.
    ID = 0 and size = 1 (no payload)
    """
    return msg.id == 0 and msg.size == 1


def is_unchoke(msg: ParsedMessage) -> bool:
    """
    Checks if the message is an 'unchoke' message.
    ID = 1 and size = 1 (no payload)
    """
    return msg.id == 1 and msg.size == 1


def is_piece(msg: ParsedMessage) -> bool:
    """
    Checks if the message is a 'piece' message.
    ID = 7 and:
        - message size is greater than 9 (header + payload)
        - payload exists (piece data)
    """
    return msg.id == 7 and msg.size > 9 and msg.payload is not None
