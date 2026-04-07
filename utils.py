from hashlib import sha256


def create_empty_grid(row: int, col: int):
    return [[0 for _ in range(col)] for _ in range(row)]


def update_direction(curr_direction, move) -> str:
    if curr_direction == "NORTH":
        if move == "L":
            return "WEST"
        return "EAST"

    if curr_direction == "WEST":
        if move == "L":
            return "SOUTH"
        return "NORTH"

    if curr_direction == "SOUTH":
        if move == "L":
            return "EAST"
        return "WEST"

    if curr_direction == "EAST":
        if move == "L":
            return "NORTH"
        return "SOUTH"

    raise ValueError(f"Unknown direction: {curr_direction}")


def disarm_mine(serial_num: str) -> int:
    pin = 0
    while True:
        temp_mine_key = str(pin) + serial_num
        hashed_data = sha256(temp_mine_key.encode()).hexdigest()
        if hashed_data[0:6] == "000000":
            return pin
        pin += 1