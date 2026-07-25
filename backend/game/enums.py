from enum import Enum, auto

class RoomState(Enum):
    WAITING = auto()  # in lobby, host hasn't started yet
    IN_PROGRESS = auto()
    FINISHED = auto()

class PlayerConnectionState(Enum):
    CONNECTED = auto()
    GRACE_PERIOD = auto() # disconnect, withing reconnect window
    KICKED = auto()

class TurnPhase(Enum):
    """
    What's currently happening for the active players's turn.
    Guessing phase runs concurrently with WORD_INPUT, so it's tracked as a flag on the room, not a separate phase here.
    """
    WORD_INPUT = auto()
    RESOLVING = auto() # word submitted, validation/scoring in progess
    TURN_COMPLETE = auto()
    