# =======================
# Module Imports
# =======================
import asyncio          # For asynchronous networking, queues, and coroutines
import os               # For file and directory operations
from typing import List # For type hinting with lists
import struct           # For packing/unpacking binary data (BitTorrent protocol operations)

# Custom utility modules
import utils.build_messages as messages       # Handles building protocol messages (handshake, requests, etc.)
import utils.verify_messages as verify        # Handles verifying message types (handshake, choke, unchoke, etc.)
from utils.details import *                   # Contains data structures like TorrentDetails, Peer, etc.
from utils.json_data import ResumeData        # For managing torrent resume data and persistence
from utils.logger import Logger, CONNECTION_LOGGER, HANDLE_LOGGER  # Logging classes for different stages
import utils.handlers as handler              # Functions to handle piece availability and verification

# =======================
# Global Constants
# =======================
TIMEOUT = 5             # Max timeout (seconds) for connections and I/O operations
NUM_CONN_TASKS = 4      # Number of workers for TCP connections and handshake stage
NUM_HANDLE_TASKS = 2    # Number of workers for handling control messages (bitfield, have, choke/unchoke)
NUM_DOWNLOAD_TASKS = 8  # Number of workers for downloading pieces (1 worker per peer)
MAX_CLAIM_PER_PEER = 30 # Max number of pieces claimed at a time per peer
BLOCK_SIZE = 2**14      # Size (16 KB) of each piece block during download


# =======================
# Connection Stage Worker
# =======================
async def connection_worker(peer_queue: asyncio.Queue, handshake_queue: asyncio.Queue, 
                            torrent_details: TorrentDetails, logger: CONNECTION_LOGGER):
    """
    Establishes TCP connections to peers and performs the BitTorrent handshake.

    Steps:
    1. Take a peer from the queue.
    2. Attempt TCP connection.
    3. Perform the BitTorrent handshake.
    4. If successful, push the connection to the handshake queue.
    """
    while True:
        try:
            peer = await peer_queue.get()
        except asyncio.QueueEmpty:
            break

        # Attempt TCP connection
        try:
            logger.tcp_connection_attempt(peer.ip, peer.port)
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(peer.ip, peer.port), timeout=TIMEOUT
            )
        except Exception as e:
            logger.tcp_connection_error(peer.ip, peer.port, f"{type(e).__name__}: {e}")
            peer_queue.task_done()
            continue

        # Perform handshake
        try:
            logger.handshake_attempt(peer.ip, peer.port)
            handshake_req = messages.build_bitTorrent_handshake(torrent_details)
            writer.write(handshake_req)
            await writer.drain()

            handshake_resp = await asyncio.wait_for(
                messages.recv_whole_message(reader, isHandshake=True), timeout=TIMEOUT
            )

            if verify.is_handshake(handshake_resp, torrent_details.info_hash):
                logger.handshake_success(peer.ip, peer.port)
            else:
                logger.handshake_failure(peer.ip, peer.port)
                writer.close()
                await writer.wait_closed()
                peer_queue.task_done()
                continue
        except Exception as e:
            logger.handshake_error(peer.ip, peer.port, str(e))
            writer.close()
            await writer.wait_closed()
            peer_queue.task_done()
            continue

        # Queue the successful connection for message handling
        await handshake_queue.put((peer, reader, writer))
        peer_queue.task_done()


# =======================
# Wait for Unchoke Helper
# =======================
async def wait_for_unchoke(reader: asyncio.StreamReader, peer: Peer, logger: HANDLE_LOGGER) -> bool:
    """
    Waits for a choke or unchoke message from the peer.
    Returns True if unchoke is received, False otherwise.
    """
    while True:
        try:
            msg = await asyncio.wait_for(messages.recv_whole_message(reader, isHandshake=False), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            print(f"Timeout while waiting for choke/unchoke from {peer}.")
            return False

        parsed = messages.parse_message(msg)

        if verify.is_unchoke(parsed):
            logger.unchoke_received(peer.ip, peer.port)
            return True
        elif verify.is_choke(parsed):
            logger.choke_received(peer.ip, peer.port)
        else:
            logger.irrelevant_message(peer.ip, peer.port)


# =======================
# Message Handling Worker
# =======================
async def handle_worker(handshake_queue: asyncio.Queue, download_queue: asyncio.Queue, 
                        resume_data: ResumeData, logger: HANDLE_LOGGER):
    """
    Handles messages after handshake:
    - Processes 'have' and 'bitfield' messages.
    - Enqueues peers into the download queue with the pieces they can serve.
    """
    while True:
        try:
            peer, reader, writer = await handshake_queue.get()
        except asyncio.TimeoutError:
            break

        try:
            # Wait for first message from peer
            msg = await asyncio.wait_for(messages.recv_whole_message(reader, isHandshake=False), timeout=TIMEOUT)
            parsed_message = messages.parse_message(msg)

            # Handle HAVE message
            if verify.is_have(parsed_message):
                logger.have_message_received(peer.ip, peer.port)

                pieces_to_request = handler.have_handler(parsed_message, resume_data.verified_pieces)
                if len(pieces_to_request) == 0:
                    logger.no_pieces_needed(peer.ip, peer.port)
                    handshake_queue.task_done()
                    continue

                # Wait for unchoke before requesting pieces
                unchoked = await wait_for_unchoke(reader, peer, logger)
                if unchoked:
                    await download_queue.put((peer, reader, writer, pieces_to_request))
                else:
                    print(f"Did not receive unchoke from {peer}. Closing connection.")
                    writer.close()
                    await writer.wait_closed()

            # Handle BITFIELD message
            elif verify.is_bitfeild(parsed_message):
                logger.bitfield_message_received(peer.ip, peer.port)

                pieces_to_request = handler.bitfield_handler(parsed_message, resume_data.verified_pieces)
                if len(pieces_to_request) == 0:
                    logger.no_pieces_needed(peer.ip, peer.port)
                    handshake_queue.task_done()
                    continue

                # Send interested message
                writer.write(messages.build_interested())
                await writer.drain()
                await download_queue.put((peer, reader, writer, pieces_to_request))

            # Unexpected message type
            else:
                print(f"Received unexpected message from {peer}")

        except Exception as e:
            logger.error_handling_message(peer.ip, peer.port, str(e))
            writer.close()
            await writer.wait_closed()

        handshake_queue.task_done()


# =======================
# Download Worker
# =======================
async def download_worker(download_queue: asyncio.Queue, torrent_details: TorrentDetails, 
                          resume_data: ResumeData, logger: Logger):
    """
    Handles downloading pieces from peers by delegating to `download_from_peer`.
    """
    while True:
        try:
            peer, reader, writer, pieces_to_request = await download_queue.get()
        except asyncio.TimeoutError:
            break

        try:
            logger.info(f"Started download from {peer.ip}:{peer.port}")
            await download_from_peer(peer, reader, writer, pieces_to_request, torrent_details, resume_data, logger)
        except Exception as e:
            logger.error(f"Download failed from {peer.ip}:{peer.port} — {e}")

        download_queue.task_done()


# =======================
# Download Logic
# =======================
async def download_from_peer(peer: Peer, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                             pieces_available_from_peer: List[int], torrent_details: TorrentDetails,
                             resume_data: ResumeData, logger: Logger):
    """
    Downloads claimed pieces block by block from a peer, verifies them, and saves them to disk.
    """
    piece_length = torrent_details.piece_length

    try:
        logger.info(f"[{peer.ip}:{peer.port}] Starting download")

        while True:
            logger.info(f"[{peer.ip}:{peer.port}] Claiming a batch to download")

            claimed = []
            # Lock to ensure safe updates to shared data
            async with resume_data.lock:
                for piece_index in pieces_available_from_peer:
                    if len(claimed) >= MAX_CLAIM_PER_PEER:
                        break
                    if not resume_data.verified_pieces[piece_index] and piece_index not in resume_data.claimed_pieces:
                        resume_data.claimed_pieces.add(piece_index)
                        claimed.append(piece_index)

            # Exit if no claimable pieces
            if not claimed:
                logger.warn(f"[{peer.ip}] No more claimable pieces. Closing connection.")
                break

            logger.info(f"[{peer.ip}:{peer.port}] Batch Claimed → {claimed}")

            # Download each claimed piece
            for piece_index in claimed:
                num_blocks = (piece_length + BLOCK_SIZE - 1) // BLOCK_SIZE
                piece_data = bytearray(piece_length)

                for block_num in range(num_blocks):
                    begin = block_num * BLOCK_SIZE
                    block_length = min(BLOCK_SIZE, piece_length - begin)

                    # Send request for the block
                    request_msg = messages.build_request(piece_index, begin, block_length)
                    writer.write(request_msg)
                    await writer.drain()

                    # Wait for the corresponding PIECE message
                    while True:
                        try:
                            msg = await messages.recv_whole_message(reader, isHandshake=False)
                            parsed = messages.parse_message(msg)

                            if verify.is_piece(parsed):
                                r_index, r_begin = struct.unpack(">II", parsed.payload[:8])
                                r_block = parsed.payload[8:]

                                if r_index == piece_index and r_begin == begin:
                                    piece_data[begin:begin + len(r_block)] = r_block
                                    break
                        except Exception as e:
                            logger.error(f"[{peer.ip}] Error during block read: {e}")
                            raise e

                # Verify the piece hash
                if not handler.verify_piece_hash(piece_data, torrent_details.hash_of_pieces[piece_index]):
                    logger.warn(f"[{peer.ip}] Invalid hash for piece {piece_index}. Discarding...")
                    async with resume_data.lock:
                        resume_data.claimed_pieces.discard(piece_index)
                    continue

                # Save piece and mark as downloaded
                save_piece_to_disk(piece_index, piece_data, torrent_details)
                logger.success(f"[{peer.ip}] Piece {piece_index} downloaded and verified ✅")

                async with resume_data.lock:
                    resume_data.verified_pieces[piece_index] = True
                    resume_data.downloaded += 1
                    resume_data.claimed_pieces.discard(piece_index)

                logger.update_stats(resume_data.downloaded, torrent_details.num_of_pieces, peer.ip)

    except Exception as e:
        logger.error(f"[{peer.ip}] Peer download error: {e}")
        async with resume_data.lock:
            for piece_index in claimed:
                resume_data.claimed_pieces.discard(piece_index)

    finally:
        writer.close()
        await writer.wait_closed()


# =======================
# Save Piece to Disk
# =======================
def save_piece_to_disk(piece_index: int, piece_data: bytes, torrent_details: TorrentDetails):
    """
    Writes the downloaded piece to its corresponding location in the files described by the torrent.
    Handles multi-file torrents by writing overlapping segments of the piece to correct files.
    """
    global_offset = piece_index * torrent_details.piece_length
    piece_size = len(piece_data)
    piece_end = global_offset + piece_size

    for file_entry in torrent_details.files:
        file_path = file_entry['path']
        file_offset = file_entry['offset']
        file_length = file_entry['length']
        file_end = file_offset + file_length

        # Calculate overlap region
        overlap_start = max(global_offset, file_offset)
        overlap_end = min(piece_end, file_end)

        if overlap_start < overlap_end:
            # Extract relevant segment from piece
            piece_data_start = overlap_start - global_offset
            piece_data_end = overlap_end - global_offset
            data_to_write = piece_data[piece_data_start:piece_data_end]

            # Offset within the file to write
            file_write_offset = overlap_start - file_offset

            # Ensure directories exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Create the file if it doesn't exist, with the correct size
            if not os.path.exists(file_path):
                with open(file_path, 'wb') as f:
                    f.truncate(file_length)

            # Write the data segment
            with open(file_path, 'r+b') as f:
                f.seek(file_write_offset)
                f.write(data_to_write)


# =======================
# Main Orchestration
# =======================
async def main(peers: list, details: TorrentDetails, resume_data: ResumeData, logger: Logger):
    """
    Orchestrates the entire download pipeline:
    1. Creates queues for connection, handshake, and download stages.
    2. Spawns worker tasks for each stage.
    3. Waits for all queues to drain.
    4. Cancels any remaining tasks.
    """
    peer_queue = asyncio.Queue()
    handshake_queue = asyncio.Queue()
    download_queue = asyncio.Queue()

    # Populate peer queue
    for peer in peers:
        await peer_queue.put(Peer(peer[0], peer[1]))

    # Start connection tasks
    tcp_bit_logger = CONNECTION_LOGGER()
    conn_tasks = [asyncio.create_task(connection_worker(peer_queue, handshake_queue, details, tcp_bit_logger))
                  for _ in range(NUM_CONN_TASKS)]

    # Start handling tasks
    handle_logger = HANDLE_LOGGER()
    handle_tasks = [asyncio.create_task(handle_worker(handshake_queue, download_queue, resume_data, handle_logger))
                    for _ in range(NUM_HANDLE_TASKS)]

    # Start download tasks
    download_tasks = [asyncio.create_task(download_worker(download_queue, details, resume_data, logger))
                      for _ in range(NUM_DOWNLOAD_TASKS)]

    # Wait for all stages to complete
    await peer_queue.join()
    await handshake_queue.join()
    await download_queue.join()

    # Cancel any pending tasks
    for task in conn_tasks + handle_tasks + download_tasks:
        task.cancel()

    print("All tasks completed.")
