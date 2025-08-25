from dataclasses import dataclass, asdict, field
from typing import List, Set
import json
from asyncio import Lock

@dataclass
class ResumeData:
    """
    A class to store and manage torrent resume data for persistence between sessions.
    """
    info_hash: str              # Unique hash identifying the torrent
    piece_length: int           # Size of each piece in bytes
    total_pieces: int           # Total number of pieces in the torrent
    downloaded: int             # Total bytes downloaded so far
    file_sizes: List[int]       # Sizes of files in the torrent
    mtime: int                  # Last modified time of the torrent files
    verified_pieces: List[bool] # Boolean list indicating verified (True) or unverified (False) pieces
    last_active: str            # Timestamp of the last activity (ISO 8601 or custom format)

    # Fields that are not included in serialization
    lock: Lock = field(init=False, repr=False, compare=False)  # Async lock for concurrency control
    claimed_pieces: Set[int] = field(default_factory=set, init=False, repr=False, compare=False)  
    # Keeps track of currently claimed pieces (not serialized)

    def __post_init__(self):
        """
        Initializes fields that are excluded from the dataclass constructor.
        """
        self.lock = Lock()

    def to_json(self, path: str) -> None:
        """
        Serializes the ResumeData object to a JSON file, 
        excluding non-serializable fields like `lock` and `claimed_pieces`.
        """
        data = asdict(self)
        data.pop('lock', None)             # Remove lock before saving
        data.pop('claimed_pieces', None)   # Remove claimed pieces before saving
        with open(path, "w") as f:
            json.dump(data, f, indent=1)

    @classmethod
    def from_json(cls, path: str) -> "ResumeData":
        """
        Deserializes a JSON file into a ResumeData object, 
        reinitializing the `lock` and `claimed_pieces` fields.
        """
        with open(path, "r") as f:
            data = json.load(f)
        obj = cls(**data)
        obj.lock = Lock()             # Reinitialize lock
        obj.claimed_pieces = set()    # Reset claimed pieces
        return obj

    def verified_to_bytes(self) -> bytes:
        """
        Converts the `verified_pieces` list of booleans into a compact bytes object.
        Each bit in a byte represents whether a piece is verified (1) or not (0).

        Example:
        [True, False, True, True, False, False, False, True] 
        -> 10110001 (0xB1)
        """
        buf = bytearray()
        byte = 0

        # Pack bits into bytes (8 pieces per byte)
        for i, bit in enumerate(self.verified_pieces):
            byte = (byte << 1) | int(bit)
            if i % 8 == 7:          # When 8 bits are collected, store the byte
                buf.append(byte)
                byte = 0

        # Handle remaining bits if total pieces are not multiple of 8
        remaining = len(self.verified_pieces) % 8
        if remaining != 0:
            byte <<= (8 - remaining)  # Shift to fill remaining bits
            buf.append(byte)

        return bytes(buf)
