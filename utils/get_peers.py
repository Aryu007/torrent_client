import struct
import socket
import random
import sys
from urllib.parse import urlparse
from typing import List, Tuple
import queue
from .logger import Logger, CONNECTION_LOGGER, HANDLE_LOGGER, TRACKER_LOGGER

# ------------------------------
# Constants
# ------------------------------
PORT_NUMBER = 6881          # Default port number used for BitTorrent peer communication
MAX_TRY = 1                 # Maximum retry attempts for requests (connection/announce)
MAX_TIME_TO_WAIT = 1        # Timeout for tracker communication in seconds

# ------------------------------
# Custom Exceptions
# ------------------------------
class InvalidConnectionRespone(Exception):
    """Raised when tracker returns an invalid response during connection request"""
    pass

class InvalidAnnounceRespone(Exception):
    """Raised when tracker returns an invalid response during announce request"""
    pass

# ------------------------------
# Function: _make_connection_request
# ------------------------------
def _make_connection_request(tracker_ip: str, tracker_port: int, count: int, logger: TRACKER_LOGGER) -> int:
    """
    Sends a connection request to a tracker to obtain a valid connection_id.
    
    Args:
        tracker_ip (str): IP address of the tracker.
        tracker_port (int): Port of the tracker.
        count (int): Retry counter for failed attempts.
        logger (TRACKER_LOGGER): Logger for connection events.

    Returns:
        int: The connection_id from the tracker to be used in announce request.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(MAX_TIME_TO_WAIT)

    protocol_id = 0x41727101980  # Predefined protocol ID for BitTorrent UDP tracker protocol
    action = 0                   # Action = 0 (connect request)
    transaction_id = random.randint(0, 2**32 - 1)  # Unique ID to match requests and responses

    # Pack data into binary format according to UDP tracker protocol spec
    connection_req = struct.pack(">QLL", protocol_id, action, transaction_id)

    # Send connection request to tracker
    try:
        logger.connection_request_sent(tracker_ip, tracker_port)
        sock.sendto(connection_req, (tracker_ip, tracker_port))
    except socket.timeout:
        logger.tracker_timeout(tracker_ip, tracker_port)
        if count == MAX_TRY:
            raise TimeoutError("Timeout Reached!")
        return _make_connection_request(tracker_ip, tracker_port, count + 1, logger)
    except socket.gaierror:
        raise socket.gaierror
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Receive response from tracker
    try:
        connection_resp, addr = sock.recvfrom(2048)
    except socket.timeout:
        logger.tracker_timeout(tracker_ip, tracker_port)
        if count == MAX_TRY:
            raise TimeoutError("Timeout Reached!")
        return _make_connection_request(tracker_ip, tracker_port, count + 1, logger)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Validate response length (must be at least 16 bytes)
    if len(connection_resp) < 16:
        logger.invalid_connection_response(tracker_ip, tracker_port)
        raise InvalidConnectionRespone("Invalid connection response from tracker!")

    # Unpack response: action, transaction_id, connection_id
    action_resp, transaction_id_resp, connection_id_resp = struct.unpack(">LLQ", connection_resp)

    # Validate action and transaction ID
    if action != action_resp:
        logger.invalid_connection_response(tracker_ip, tracker_port)
        raise InvalidConnectionRespone("Invalid connection response from tracker: action mismatch!")
    if transaction_id != transaction_id_resp:
        logger.invalid_connection_response(tracker_ip, tracker_port)
        raise InvalidConnectionRespone("Invalid connection response from tracker: transaction ID mismatch!")

    return connection_id_resp

# ------------------------------
# Function: get_interval_data
# ------------------------------
def get_interval_data() -> List[int]:
    """
    Returns tracker interval and current swarm info.

    Returns:
        List[int]: [interval_seconds, num_seeders, num_leechers]
    """
    return [Interval, Seeder, Leecher]

# ------------------------------
# Function: _make_announce_request
# ------------------------------
def _make_announce_request(connection_id: int, info_hash: bytes, total_length: int,
                           tracker_ip: str, tracker_port: int, count: int, logger: TRACKER_LOGGER) -> List[Tuple[str, int]]:
    """
    Sends an announce request to the tracker to retrieve peer information.

    Args:
        connection_id (int): Connection ID obtained from connection request.
        info_hash (bytes): SHA1 hash of torrent's info dictionary.
        total_length (int): Total size of files in torrent.
        tracker_ip (str): Tracker IP address.
        tracker_port (int): Tracker port number.
        count (int): Retry attempt counter.
        logger (TRACKER_LOGGER): Logger for announce events.

    Returns:
        List[Tuple[str, int]]: List of peers as (IP, port) tuples.
    """
    transaction_id = random.randint(0, 2**32 - 1)
    peer_id = b'-TR4003-' + bytes(random.getrandbits(8) for _ in range(12))  # Random peer ID
    port = PORT_NUMBER
    action = 1  # Action = 1 (announce)
    
    downloaded = 0
    left = total_length
    uploaded = 0
    event = 2  # 2 = started event
    ip = 0
    key = random.randint(0, 2**32 - 1)
    num_want = -1  # Request as many peers as possible

    # Pack announce request
    announce_req = struct.pack(">QLL20s20sQQQLLLlH",
                               connection_id, action, transaction_id, info_hash, peer_id,
                               downloaded, left, uploaded, event, ip, key, num_want, port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(MAX_TIME_TO_WAIT)

    logger.announce_request_sent(tracker_ip, tracker_port)

    # Send announce request
    try:
        sock.sendto(announce_req, (tracker_ip, tracker_port))
    except socket.timeout:
        logger.tracker_timeout(tracker_ip, tracker_port)
        if count == MAX_TRY:
            raise TimeoutError("Timeout Reached!")
        return _make_announce_request(connection_id, info_hash, total_length, tracker_ip, tracker_port, count + 1, logger)
    except socket.gaierror:
        raise socket.gaierror
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

    logger.announce_response_received(tracker_ip, tracker_port)

    # Receive announce response
    try:
        announce_resp, addr = sock.recvfrom(4096)
    except socket.timeout:
        logger.tracker_timeout(tracker_ip, tracker_port)
        if count == MAX_TRY:
            raise TimeoutError("Timeout Reached!")
        return _make_announce_request(connection_id, info_hash, total_length, tracker_ip, tracker_port, count + 1, logger)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

    # Validate response length
    if len(announce_resp) < 20:
        logger.invalid_announce_response(tracker_ip, tracker_port)
        raise InvalidAnnounceRespone("Invalid announce response: response shorter than 20 bytes!")

    # Unpack first 20 bytes for swarm info
    action_resp, transaction_id_resp, interval, leechers, seeders = struct.unpack(">LLLLL", announce_resp[0:20])

    # Update global swarm data for stats
    global Interval, Seeder, Leecher
    Interval = interval
    Seeder = seeders
    Leecher = leechers

    # Validate response
    if action != action_resp:
        logger.invalid_announce_response(tracker_ip, tracker_port)
        raise InvalidAnnounceRespone("Invalid announce response: action mismatch!")
    if transaction_id != transaction_id_resp:
        logger.invalid_announce_response(tracker_ip, tracker_port)
        raise InvalidAnnounceRespone("Invalid announce response: transaction ID mismatch!")

    # Parse peers (6 bytes per peer: 4 bytes IP, 2 bytes port)
    peers = []
    offset = 20
    while offset < len(announce_resp):
        ip_packed = announce_resp[offset:offset + 4]
        port_packed = announce_resp[offset + 4:offset + 6]

        ip = socket.inet_ntoa(ip_packed)
        port = struct.unpack(">H", port_packed)[0]

        peers.append((ip, port))
        offset += 6

    logger.peers_received(tracker_ip, tracker_port, len(peers))
    return peers

# ------------------------------
# Function: get_peers_list
# ------------------------------
def get_peers_list(torrent_info: dict, info_hash: bytes, peer_list: queue.Queue, logger: Logger) -> None:
    """
    Extracts tracker URLs from torrent file, contacts trackers,
    and populates the peer list queue with active peers.

    Args:
        torrent_info (dict): Decoded torrent metadata.
        info_hash (bytes): SHA1 hash of torrent info dictionary.
        peer_list (queue.Queue): Shared queue for peer data.
        logger (Logger): Logger for logging events.
    """
    tracker_url_list = []

    # Extract trackers from torrent metadata
    try:
        tracker_url_list.append(torrent_info[b'announce'].decode('utf-8'))

        if b'announce-list' in torrent_info:
            announce_list = torrent_info[b'announce-list']
            if announce_list[0][0].decode('utf-8') not in tracker_url_list:
                tracker_url_list.append(announce_list[0][0].decode('utf-8'))
            for url in announce_list[1:]:
                tracker_url_list.append(url[0].decode('utf-8'))

    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    # Calculate total size of files for this torrent
    try:
        total_length = 0
        info_dict = torrent_info[b'info']
        if b'files' in info_dict:
            for file in info_dict[b'files']:
                total_length += file[b'length']
        else:
            total_length += info_dict[b'length']
    except Exception as E:
        print(f"Error : {E}")
        sys.exit(1)

    # Iterate through all trackers and attempt to retrieve peers
    for url in tracker_url_list:
        parsed_url = urlparse(url)
        tracker_ip = parsed_url.hostname
        tracker_port = parsed_url.port
        tracker_logger = TRACKER_LOGGER()

        # Step 1: Establish connection with tracker
        try:
            connection_id = _make_connection_request(tracker_ip, tracker_port, 1, tracker_logger)
        except socket.gaierror:
            print("DNS lookup failed, trying next tracker!")
            continue
        except TimeoutError:
            print("Tracker timed out, trying next tracker!")
            continue
        except InvalidAnnounceRespone as inv:
            print(inv, "Trying next tracker!")
            continue
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

        # Step 2: Announce to tracker and get peer list
        try:
            peers = _make_announce_request(connection_id, info_hash, total_length, tracker_ip, tracker_port, 1, tracker_logger)
            peer_list.put(peers)
        except TimeoutError:
            continue
        except InvalidAnnounceRespone as inv:
            print(inv)
            continue
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

# Exported functions
__all__ = ["get_peers_list", "get_interval_data"]
