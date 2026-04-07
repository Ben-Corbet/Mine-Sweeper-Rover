from __future__ import annotations

import asyncio
import random
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import utils

NOT_STARTED = "NOT_STARTED"
FINISHED = "FINISHED"
MOVING = "MOVING"
ELIMINATED = "ELIMINATED"

NORTH = "NORTH"
EAST = "EAST"
SOUTH = "SOUTH"
WEST = "WEST"

VALID_COMMANDS = {"L", "R", "M", "D"}

app = FastAPI(title="Rover Minefield API")

origins = [
    "http://localhost",
    "http://localhost:80",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="dist", html=True), name="static")
templates = Jinja2Templates(directory="dist")


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


DEFAULT_ROWS = 10
DEFAULT_COLS = 10

grid = utils.create_empty_grid(DEFAULT_ROWS, DEFAULT_COLS)
mines: List[Dict] = []
rovers: List[Dict] = []

mine_ids = random.sample(range(1000, 1000000), 5000)
rover_ids = random.sample(range(100, 1000), 900)


class MapDimensions(BaseModel):
    row: int = Field(..., ge=1)
    col: int = Field(..., ge=1)


class MineCreate(BaseModel):
    row: int = Field(..., ge=0)
    col: int = Field(..., ge=0)
    serialNum: Optional[int] = Field(default=None, ge=1)


class MineUpdate(BaseModel):
    row: Optional[int] = Field(default=None, ge=0)
    col: Optional[int] = Field(default=None, ge=0)
    serialNum: Optional[int] = Field(default=None, ge=1)


class RoverCreate(BaseModel):
    commands: str


class RoverUpdate(BaseModel):
    commands: str


def get_rows() -> int:
    return len(grid)


def get_cols() -> int:
    return len(grid[0]) if grid else 0


def ensure_in_bounds(row: int, col: int) -> bool:
    return 0 <= row < get_rows() and 0 <= col < get_cols()


def rebuild_grid() -> None:
    global grid
    grid = utils.create_empty_grid(get_rows(), get_cols())
    for mine in mines:
        if ensure_in_bounds(mine["row"], mine["col"]):
            grid[mine["row"]][mine["col"]] = 2 if mine["status"] == "DISARMED" else 1
    grid[0][0] = 0


def resize_grid(rows: int, cols: int) -> None:
    global grid, mines
    grid = utils.create_empty_grid(rows, cols)
    mines = [m for m in mines if 0 <= m["row"] < rows and 0 <= m["col"] < cols]
    rebuild_grid()


def normalize_commands(command_string: str) -> str:
    if not isinstance(command_string, str) or not command_string.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Command list must be a non-empty string containing only "L", "R", "M", "D".',
        )

    normalized = command_string.strip().upper()
    for command in normalized:
        if command not in VALID_COMMANDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid command found. Commands must only contain "L", "R", "M", "D".',
            )
    return normalized


def find_mine_by_id(mine_id: int) -> Optional[Dict]:
    for mine in mines:
        if mine["id"] == mine_id:
            return mine
    return None


def mine_at(row: int, col: int) -> Optional[Dict]:
    for mine in mines:
        if mine["row"] == row and mine["col"] == col:
            return mine
    return None


def active_mine_at(row: int, col: int) -> Optional[Dict]:
    for mine in mines:
        if mine["row"] == row and mine["col"] == col and mine["status"] == "ACTIVE":
            return mine
    return None


def find_rover(rover_id: int) -> Optional[Dict]:
    for rover in rovers:
        if rover["id"] == rover_id:
            return rover
    return None


def rover_response(rover: Dict) -> Dict:
    return {
        "id": rover["id"],
        "status": rover["status"],
        "row": rover["position"]["row"],
        "col": rover["position"]["col"],
        "x": rover["position"]["col"],
        "y": rover["position"]["row"],
        "direction": rover["direction"],
        "commands": rover["commands"],
        "executed_commands": rover["executed_commands"],
        "pins": rover["pins"],
        "path": rover["path"],
    }


def step_forward(position: Dict, direction: str) -> Dict:
    row = position["row"]
    col = position["col"]

    if direction == NORTH:
        row -= 1
    elif direction == SOUTH:
        row += 1
    elif direction == EAST:
        col += 1
    elif direction == WEST:
        col -= 1

    return {"row": row, "col": col}


@app.get("/map", status_code=status.HTTP_200_OK)
def get_map():
    return {
        "row": get_rows(),
        "col": get_cols(),
        "map": grid,
    }


@app.put("/map", status_code=status.HTTP_201_CREATED)
def update_map(item: MapDimensions):
    resize_grid(item.row, item.col)
    return {
        "row": item.row,
        "col": item.col,
        "map": grid,
    }


@app.get("/mines")
def get_mines():
    return mines


@app.get("/mines/{mine_id}")
def get_mine(mine_id: int):
    mine = find_mine_by_id(mine_id)
    if not mine:
        raise HTTPException(status_code=404, detail="Mine not found.")
    return mine


@app.post("/mines", status_code=status.HTTP_201_CREATED)
def create_mine(payload: MineCreate):
    if not ensure_in_bounds(payload.row, payload.col):
        raise HTTPException(status_code=400, detail="Mine coordinates are outside map bounds.")

    if mine_at(payload.row, payload.col):
        raise HTTPException(status_code=400, detail="A mine already exists at the given location.")

    mine_id = payload.serialNum if payload.serialNum is not None else mine_ids.pop()

    if find_mine_by_id(mine_id):
        raise HTTPException(status_code=400, detail="Mine serial/id already exists.")

    mine = {
        "id": mine_id,
        "row": payload.row,
        "col": payload.col,
        "serialNum": mine_id,
        "status": "ACTIVE",
    }
    mines.append(mine)
    grid[payload.row][payload.col] = 1

    return {"id": mine_id, "mine": mine}


@app.put("/mines/{mine_id}")
def update_mine(mine_id: int, payload: MineUpdate):
    mine = find_mine_by_id(mine_id)
    if not mine:
        raise HTTPException(status_code=404, detail="Mine not found.")

    new_row = payload.row if payload.row is not None else mine["row"]
    new_col = payload.col if payload.col is not None else mine["col"]
    new_serial = payload.serialNum if payload.serialNum is not None else mine["serialNum"]

    if not ensure_in_bounds(new_row, new_col):
        raise HTTPException(status_code=400, detail="Updated coordinates are outside map bounds.")

    existing = mine_at(new_row, new_col)
    if existing and existing["id"] != mine_id:
        raise HTTPException(status_code=400, detail="Another mine already exists at the new location.")

    if new_serial != mine["serialNum"] and find_mine_by_id(new_serial):
        raise HTTPException(status_code=400, detail="Another mine already uses that serial/id.")

    old_row = mine["row"]
    old_col = mine["col"]

    mine["row"] = new_row
    mine["col"] = new_col
    mine["serialNum"] = new_serial
    mine["id"] = new_serial

    if ensure_in_bounds(old_row, old_col):
        grid[old_row][old_col] = 0
    grid[new_row][new_col] = 2 if mine["status"] == "DISARMED" else 1

    return mine


@app.delete("/mines/{mine_id}")
def delete_mine(mine_id: int):
    for i, mine in enumerate(mines):
        if mine["id"] == mine_id:
            if ensure_in_bounds(mine["row"], mine["col"]):
                grid[mine["row"]][mine["col"]] = 0
            mines.pop(i)
            return {"message": f"Mine {mine_id} deleted."}

    raise HTTPException(status_code=404, detail="Mine not found.")


@app.get("/rovers")
def get_rovers():
    return [rover_response(rover) for rover in rovers]


@app.get("/rovers/{rover_id}")
def get_rover(rover_id: int):
    rover = find_rover(rover_id)
    if not rover:
        raise HTTPException(status_code=404, detail=f"Rover with id {rover_id} not found.")
    return rover_response(rover)


@app.post("/rovers", status_code=status.HTTP_201_CREATED)
def create_rover(payload: RoverCreate):
    command_string = normalize_commands(payload.commands)

    rover = {
        "id": rover_ids.pop(),
        "commands": command_string,
        "status": NOT_STARTED,
        "position": {"row": 0, "col": 0},
        "direction": EAST,
        "executed_commands": [],
        "pins": [],
        "path": [{"row": 0, "col": 0, "step": 0}],
        "busy": False,
    }
    rovers.append(rover)
    return rover_response(rover)


@app.put("/rovers/{rover_id}")
def update_rover(rover_id: int, payload: RoverUpdate):
    rover = find_rover(rover_id)
    if not rover:
        raise HTTPException(status_code=404, detail=f"Rover with id {rover_id} not found.")

    if rover["status"] == FINISHED:
        raise HTTPException(status_code=400, detail="Cannot update commands for a finished rover.")

    if rover["busy"]:
        raise HTTPException(status_code=409, detail="Rover is currently busy.")

    rover["commands"] = normalize_commands(payload.commands)
    rover["status"] = NOT_STARTED
    rover["position"] = {"row": 0, "col": 0}
    rover["direction"] = EAST
    rover["executed_commands"] = []
    rover["pins"] = []
    rover["path"] = [{"row": 0, "col": 0, "step": 0}]

    return rover_response(rover)


@app.delete("/rovers/{rover_id}")
def delete_rover(rover_id: int):
    for i, rover in enumerate(rovers):
        if rover["id"] == rover_id:
            rovers.pop(i)
            return {"message": f"Rover {rover_id} deleted."}
    raise HTTPException(status_code=404, detail=f"Rover with id {rover_id} not found.")


@app.post("/rovers/{rover_id}/dispatch")
async def dispatch_rover(rover_id: int):
    rover = find_rover(rover_id)
    if not rover:
        raise HTTPException(status_code=404, detail=f"Rover with id {rover_id} not found.")

    if rover["busy"]:
        raise HTTPException(status_code=409, detail="Rover is currently busy.")

    if not rover["commands"]:
        raise HTTPException(status_code=400, detail="Rover has no commands to dispatch.")

    rover["busy"] = True
    rover["status"] = MOVING

    try:
        for cmd in rover["commands"]:
            if cmd in {"L", "R"}:
                rover["direction"] = utils.update_direction(rover["direction"], cmd)
                rover["executed_commands"].append(cmd)

            elif cmd == "M":
                current_row = rover["position"]["row"]
                current_col = rover["position"]["col"]

                # Rover only explodes when trying to move OFF an active mine
                current_mine = active_mine_at(current_row, current_col)
                if current_mine:
                    rover["executed_commands"].append(cmd)
                    rover["status"] = ELIMINATED
                    return {
                        "message": f'Rover moved off active mine {current_mine["id"]} and was eliminated.',
                        **rover_response(rover),
                        "map": grid,
                    }

                new_pos = step_forward(rover["position"], rover["direction"])

                if not ensure_in_bounds(new_pos["row"], new_pos["col"]):
                    rover["executed_commands"].append(cmd)
                    rover["status"] = ELIMINATED
                    return {
                        "message": "Rover moved out of bounds and was eliminated.",
                        **rover_response(rover),
                        "map": grid,
                    }

                rover["position"] = new_pos
                rover["path"].append(
                    {
                        "row": new_pos["row"],
                        "col": new_pos["col"],
                        "step": len(rover["executed_commands"]) + 1,
                    }
                )
                rover["executed_commands"].append(cmd)

            elif cmd == "D":
                mine = active_mine_at(rover["position"]["row"], rover["position"]["col"])
                rover["executed_commands"].append(cmd)

                if mine:
                    pin = await asyncio.to_thread(utils.disarm_mine, str(mine["serialNum"]))
                    mine["status"] = "DISARMED"
                    rebuild_grid()
                    rover["pins"].append({"mineId": mine["id"], "pin": pin})

        rover["status"] = FINISHED
        return {
            "message": "Rover finished executing command list.",
            **rover_response(rover),
            "map": grid,
        }

    finally:
        rover["busy"] = False