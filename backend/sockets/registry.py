"""
Shared sid <-> player mappings, used across all socket handler files.
Kept separate specifically to avoid handler files importing each other.
"""

_sid_to_player: dict[str,tuple[str,str]] = {} # sid -> (room_code,player_id)
_player_to_sid:dict[str,str] = {} # player_id -> sid

def register(sid:str,room_code:str,player_id:str) -> None:
    _sid_to_player[sid] = (room_code,player_id)
    _player_to_sid[player_id] = sid

def unregister_sid(sid:str) -> tuple[str,str] | None:
    entry = _sid_to_player.pop(sid,None)
    if entry:
        _player_to_sid.pop(entry[1],None)
    return entry

def get_sid_for_player(player_id:str) -> str | None:
    return _player_to_sid.get(player_id)

def get_player_for_sid(sid:str) -> tuple[str,str] | None:
    return _sid_to_player.get(sid)

def _reset_for_tests() -> None:
    _sid_to_player.clear()
    _player_to_sid.clear()

