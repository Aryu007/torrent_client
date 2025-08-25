import time
import threading

class Logger:
    """
    Base Logger class to manage common logging functionality.
    Handles download stats and progress visualization in the console.
    """
    def __init__(self):
        self.start_time = time.time()  # Time when logging started
        self.downloaded = 0            # Number of pieces downloaded so far
        self.total = 1                 # Total pieces (defaulted to avoid division errors)
        self.active_peers = set()      # Set to store currently active peers
        self.lock = threading.Lock()   # Lock for thread-safe updates

    # General logging methods with color-coded output for better visibility
    def success(self, msg: str):
        print(f"\033[92m✅ {msg}\033[0m")  # Green for success messages

    def error(self, msg: str):
        print(f"\033[91m❌ {msg}\033[0m")  # Red for error messages

    def info(self, msg: str):
        print(f"\033[94mℹ️  {msg}\033[0m")  # Blue for informational messages

    def warn(self, msg: str):
        print(f"\033[93m⚠️  {msg}\033[0m")  # Yellow for warnings

    def update_stats(self, downloaded: int, total: int, peer_ip=None):
        """
        Update the current download stats.
        :param downloaded: Number of pieces downloaded
        :param total: Total number of pieces
        :param peer_ip: Optional, IP of the peer contributing to the download
        """
        with self.lock:
            self.downloaded = downloaded
            self.total = total
            if peer_ip:
                self.active_peers.add(peer_ip)  # Track unique active peers

    def display_stats_loop(self, interval=10):
        """
        Periodically display the current download progress and elapsed time.
        Runs in a daemon thread to avoid blocking the main process.
        :param interval: Time interval (seconds) to refresh stats
        """
        def loop():
            while True:
                with self.lock:
                    percent = (self.downloaded / self.total) * 100
                    elapsed = time.time() - self.start_time
                    print("\n\033[96m" + "━" * 40)
                    print(f"📦 Progress: {self.downloaded}/{self.total} pieces ({percent:.2f}%)")
                    print(f"⏱️  Time Elapsed: {int(elapsed)} sec")
                    # Uncomment to show active peers:
                    # print(f"🧑‍🤝‍🧑 Active Peers: {len(self.active_peers)}")
                    print("━" * 40 + "\033[0m\n")
                time.sleep(interval)

        # Run the loop in a daemon thread
        threading.Thread(target=loop, daemon=True).start()


class CONNECTION_LOGGER(Logger):
    """
    Specialized logger for TCP connections and BitTorrent handshakes with peers.
    """
    def tcp_connection_attempt(self, peer_ip: str, peer_port: int):
        print(f"\033[95m🌐 Trying TCP connection to {peer_ip}:{peer_port}\033[0m")

    def tcp_connection_error(self, peer_ip: str, peer_port: int, error: str):
        print(f"\033[91m❌ Cannot make TCP connection with {peer_ip}:{peer_port}, Error: {error}\033[0m")

    def handshake_attempt(self, peer_ip: str, peer_port: int):
        print(f"\033[95m🔐 Trying BitTorrent handshake with {peer_ip}:{peer_port}\033[0m")

    def handshake_success(self, peer_ip: str, peer_port: int):
        print(f"\033[92m✅ BitTorrent handshake successful with {peer_ip}:{peer_port}\033[0m")

    def handshake_failure(self, peer_ip: str, peer_port: int):
        print(f"\033[91m❌ Invalid handshake response from {peer_ip}:{peer_port}\033[0m")

    def handshake_error(self, peer_ip: str, peer_port: int, error: str):
        print(f"\033[91m❌ Handshake failed with {peer_ip}:{peer_port}, Error: {error}\033[0m")


class HANDLE_LOGGER(Logger):
    """
    Specialized logger for handling messages and states during data exchange with peers.
    """
    def waiting_for_unchoke(self, peer_ip: str, peer_port: int):
        print(f"\033[95m⏳ Waiting for unchoke from {peer_ip}:{peer_port}...\033[0m")

    def unchoke_received(self, peer_ip: str, peer_port: int):
        print(f"\033[92m✅ {peer_ip}:{peer_port} unchoked us. Proceeding to download.\033[0m")

    def choke_received(self, peer_ip: str, peer_port: int):
        print(f"\033[93m⚠️ {peer_ip}:{peer_port} is choked, waiting for unchoke...\033[0m")

    def irrelevant_message(self, peer_ip: str, peer_port: int):
        print(f"\033[93m⚠️ Received irrelevant message from {peer_ip}:{peer_port} while waiting for unchoke.\033[0m")

    def have_message_received(self, peer_ip: str, peer_port: int):
        print(f"\033[94mℹ️ Received 'have' message from {peer_ip}:{peer_port}\033[0m")

    def bitfield_message_received(self, peer_ip: str, peer_port: int):
        print(f"\033[94mℹ️ Received 'bitfield' message from {peer_ip}:{peer_port}\033[0m")

    def no_pieces_needed(self, peer_ip: str, peer_port: int):
        print(f"\033[95m🛑 No pieces needed from {peer_ip}:{peer_port}\033[0m")

    def failed_handling_have(self, peer_ip: str, peer_port: int, error: str):
        print(f"\033[91m❌ Failed handling 'have' from {peer_ip}:{peer_port}, Error: {error}\033[0m")

    def failed_handling_bitfield(self, peer_ip: str, peer_port: int, error: str):
        print(f"\033[91m❌ Failed sending 'interested' to {peer_ip}:{peer_port} in response to bitfield, Error: {error}\033[0m")
    
    def error_handling_message(self, peer_ip: str, peer_port: int, error: str):
        print(f"\033[91m❌ Error handling message from {peer_ip}:{peer_port}, Error: {error}\033[0m")


class TRACKER_LOGGER(Logger):
    """
    Specialized logger for interactions with the tracker.
    Logs connection attempts, responses, and peer lists.
    """
    def connection_request_sent(self, tracker_ip: str, tracker_port: int):
        print(f"\033[94mℹ️ Connection request sent to tracker: {tracker_ip}:{tracker_port}\033[0m")

    def connection_response_received(self, tracker_ip: str, tracker_port: int):
        print(f"\033[92m✅ Connection response received from tracker: {tracker_ip}:{tracker_port}\033[0m")

    def announce_request_sent(self, tracker_ip: str, tracker_port: int):
        print(f"\033[94mℹ️ Announce request sent to tracker: {tracker_ip}:{tracker_port}\033[0m")

    def announce_response_received(self, tracker_ip: str, tracker_port: int):
        print(f"\033[92m✅ Announce response received from tracker: {tracker_ip}:{tracker_port}\033[0m")

    def tracker_timeout(self, tracker_ip: str, tracker_port: int):
        print(f"\033[91m❌ Timeout while connecting to tracker: {tracker_ip}:{tracker_port}\033[0m")

    def invalid_connection_response(self, tracker_ip: str, tracker_port: int):
        print(f"\033[91m❌ Invalid connection response from tracker: {tracker_ip}:{tracker_port}\033[0m")

    def invalid_announce_response(self, tracker_ip: str, tracker_port: int):
        print(f"\033[91m❌ Invalid announce response from tracker: {tracker_ip}:{tracker_port}\033[0m")

    def peers_received(self, tracker_ip: str, tracker_port: int, num_peers: int):
        print(f"\033[94mℹ️ Received {num_peers} peers from tracker: {tracker_ip}:{tracker_port}\033[0m")

    def failed_to_connect(self, tracker_ip: str, tracker_port: int):
        print(f"\033[91m❌ Failed to connect to tracker: {tracker_ip}:{tracker_port}\033[0m")
