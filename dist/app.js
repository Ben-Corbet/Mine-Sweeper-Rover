const BASE_URL = window.location.origin;

let currentMap = [];
let currentRover = null;

async function apiFetch(endpoint, options = {}) {
  const response = await fetch(`${BASE_URL}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message = data?.detail || `Request failed: ${response.status}`;
    throw new Error(message);
  }

  return data;
}

function setInfo(html) {
  document.getElementById("info").innerHTML = html;
}

function updateRoverLabel() {
  const label = document.getElementById("rover");
  label.textContent = `Rover Id: ${currentRover ? currentRover.id : "none"}`;
}

function buildPathIndex(path = []) {
  const index = {};
  for (const point of path) {
    const key = `${point.row},${point.col}`;
    if (!index[key]) index[key] = [];
    index[key].push(point.step);
  }
  return index;
}

function renderMap(grid, rover = null) {
  const mapDiv = document.getElementById("map");
  mapDiv.innerHTML = "";

  const pathIndex = buildPathIndex(rover?.path || []);
  const roverRow = rover?.row;
  const roverCol = rover?.col;

  grid.forEach((row, i) => {
    const rowDiv = document.createElement("div");
    rowDiv.className = "row";

    row.forEach((cell, j) => {
      const cellDiv = document.createElement("div");
      cellDiv.className = "cell";

      if (cell === 1) {
        cellDiv.classList.add("mine");
      } else if (cell === 2) {
        cellDiv.classList.add("disarmed");
      }

      const key = `${i},${j}`;
      if (pathIndex[key]) {
        cellDiv.textContent = pathIndex[key].join(",");
      }

      if (roverRow === i && roverCol === j) {
        cellDiv.classList.add("rover-marker");
        cellDiv.textContent = cellDiv.textContent ? `${cellDiv.textContent} R` : "R";
      }

      rowDiv.appendChild(cellDiv);
    });

    mapDiv.appendChild(rowDiv);
  });
}

function renderRoverInfo(data, heading = "Rover Update") {
  const pins = (data.pins || [])
    .map((p) => `<li>Mine ${p.mineId}: PIN ${p.pin}</li>`)
    .join("");

  setInfo(`
    <h3>${heading}</h3>
    <p><strong>Status:</strong> ${data.status}</p>
    <p><strong>Position:</strong> (${data.row}, ${data.col})</p>
    <p><strong>Direction:</strong> ${data.direction}</p>
    <p><strong>Commands:</strong> ${data.commands || ""}</p>
    <p><strong>Executed:</strong> ${(data.executed_commands || []).join("")}</p>
    <p><strong>Message:</strong> ${data.message || ""}</p>
    <div>
      <strong>Disarmed Pins:</strong>
      <ul>${pins || "<li>None</li>"}</ul>
    </div>
  `);
}

async function loadMap() {
  try {
    const data = await apiFetch("/map");
    currentMap = data.map;
    renderMap(currentMap, currentRover);
  } catch (error) {
    setInfo(`<p class="error">${error.message}</p>`);
  }
}

async function createRover(commands) {
  const data = await apiFetch("/rovers", {
    method: "POST",
    body: JSON.stringify({ commands }),
  });

  currentRover = data;
  updateRoverLabel();
  renderRoverInfo(data, "Rover Created");
  renderMap(currentMap, currentRover);
}

async function dispatchRover() {
  if (!currentRover) {
    setInfo(`<p class="error">Create a rover first.</p>`);
    return;
  }

  try {
    const data = await apiFetch(`/rovers/${currentRover.id}/dispatch`, {
      method: "POST",
    });

    currentRover = data;
    currentMap = data.map || currentMap;
    updateRoverLabel();
    renderRoverInfo(data, "Dispatch Complete");
    renderMap(currentMap, currentRover);
  } catch (error) {
    setInfo(`<p class="error">${error.message}</p>`);
  }
}

async function createMine(row, col, serialNum) {
  const body = {
    row: Number(row),
    col: Number(col),
  };

  if (serialNum !== "") {
    body.serialNum = Number(serialNum);
  }

  const data = await apiFetch("/mines", {
    method: "POST",
    body: JSON.stringify(body),
  });

  await loadMap();
  setInfo(`
    <h3>Mine Created</h3>
    <p><strong>Mine ID:</strong> ${data.id}</p>
    <p><strong>Row:</strong> ${data.mine.row}</p>
    <p><strong>Col:</strong> ${data.mine.col}</p>
  `);
}

document.getElementById("manualCommandForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("manual-commands").value.trim();

  if (!input) return;

  try {
    await createRover(input);
  } catch (error) {
    setInfo(`<p class="error">${error.message}</p>`);
  }
});

document.getElementById("mineForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const row = document.getElementById("mine-row").value;
  const col = document.getElementById("mine-col").value;
  const serial = document.getElementById("mine-serial").value;

  try {
    await createMine(row, col, serial);
    e.target.reset();
  } catch (error) {
    setInfo(`<p class="error">${error.message}</p>`);
  }
});

document.getElementById("start").addEventListener("click", dispatchRover);
document.getElementById("refreshMap").addEventListener("click", loadMap);

window.onload = async () => {
  updateRoverLabel();
  await loadMap();
};