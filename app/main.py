#!/usr/bin/env python3
import asyncio
import dataclasses
import logging.handlers
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path

import requests
from litestar import Litestar, get
from litestar.controller import Controller
from litestar.datastructures import State
from litestar.logging import LoggingConfig
from litestar.static_files.config import StaticFilesConfig

from network_sampler import NetworkSampler
from telemetry_sampler import read_telem

SAMPLE_PERIOD_SECONDS = 1

log_dir = Path('/app/logs')
db_path = log_dir / "networkTelem.db"


class CountController(Controller):
    COUNT_VAR = 'quickstart_backend_perm_count'
    def __init__(self, *args, **kwargs):
        self._temp_count = 0
        super().__init__(*args, **kwargs)

    @get("/temp_count", sync_to_thread=False)
    def increment_temp_count(self) -> dict[str, int]:
        self._temp_count += 1
        return {"value": self._temp_count}

    @get("/persistent_count", sync_to_thread=True)
    def increment_persistent_count(self, state: State) -> dict[str, int]:
        try:
            response = requests.get(f'{state.bag_url}/get/{self.COUNT_VAR}')
            response.raise_for_status()
            value = response.json()['value']
        except Exception:
            value = 0
        value += 1
        output = {'value': value}
        requests.post(f'{state.bag_url}/set/{self.COUNT_VAR}', json=output)
        return output


def init_db(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            eth0_bps_sent REAL, eth0_bps_recv REAL, eth0_pps_sent REAL, eth0_pps_recv REAL, eth0_errin_ps REAL, eth0_errout_ps REAL, eth0_dropin_ps REAL, eth0_dropout_ps REAL,
            wlan0_bps_sent REAL, wlan0_bps_recv REAL, wlan0_pps_sent REAL, wlan0_pps_recv REAL, wlan0_errin_ps REAL, wlan0_errout_ps REAL, wlan0_dropin_ps REAL, wlan0_dropout_ps REAL,
            pitch REAL, roll REAL, yaw REAL, heading REAL, groundspeed REAL
        )
    """)
    conn.commit()
    return conn


def flatten_network_result(iface, network_result):
    flattened = {}
    for key in network_result[iface].keys():
        flattened[f"{iface}_{key}"] = network_result[iface][key]
    return flattened


def write_sample(conn, network_result, telem_result, timestamp):
    sql_query = """
        INSERT INTO samples (timestamp,
            eth0_bps_sent, eth0_bps_recv, eth0_pps_sent, eth0_pps_recv, eth0_errin_ps, eth0_errout_ps, eth0_dropin_ps, eth0_dropout_ps,
            wlan0_bps_sent, wlan0_bps_recv, wlan0_pps_sent, wlan0_pps_recv, wlan0_errin_ps, wlan0_errout_ps, wlan0_dropin_ps, wlan0_dropout_ps,
            roll, pitch, yaw, heading, groundspeed)
        VALUES (:timestamp, :eth0_bps_sent, :eth0_bps_recv, :eth0_pps_sent, :eth0_pps_recv, :eth0_errin_ps, :eth0_errout_ps, :eth0_dropin_ps, :eth0_dropout_ps, :wlan0_bps_sent, :wlan0_bps_recv, :wlan0_pps_sent, :wlan0_pps_recv, :wlan0_errin_ps, :wlan0_errout_ps, :wlan0_dropin_ps, :wlan0_dropout_ps, :roll, :pitch, :yaw, :heading, :groundspeed)
    """
    cursor = conn.cursor()
    table_data = (
        flatten_network_result('eth0', network_result)
        | flatten_network_result('wlan0', network_result)
        | dataclasses.asdict(telem_result)
        | {'timestamp': timestamp}
    )
    cursor.execute(sql_query, table_data)
    conn.commit()


@get("/api/history")
async def get_history(state: State, limit: int = 120) -> list[dict]:
    cursor = state.db_conn.cursor()
    cursor.execute("SELECT * FROM samples ORDER BY id DESC LIMIT ?", (limit,))
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in reversed(rows)]


async def sampling_loop(app: Litestar) -> None:
    network_sampler = NetworkSampler()
    conn = app.state.db_conn
    while True:
        try:
            timestamp = time.time()
            # nS.sample() and read_telem() both do blocking I/O (psutil syscalls / requests.get) -
            # run them off the event loop so they don't stall the web server while they wait.
            network_sample = await asyncio.to_thread(network_sampler.sample)
            telem_sample = await asyncio.to_thread(read_telem)
            if telem_sample is not None:
                write_sample(conn, network_sample, telem_sample, timestamp)
            else:
                app.logger.warning("Skipping sample - telemetry read failed.")
        except Exception:
            app.logger.exception("Sampling loop iteration failed, continuing.")
        await asyncio.sleep(SAMPLE_PERIOD_SECONDS)


@asynccontextmanager
async def sampling_lifespan(app: Litestar):
    app.state.db_conn = init_db(db_path)
    task = asyncio.create_task(sampling_loop(app))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        app.state.db_conn.close()


logging_config = LoggingConfig(
    loggers={
        __name__: dict(
            level='INFO',
            handlers=['queue_listener'],
        )
    },
)

log_dir.mkdir(parents=True, exist_ok=True)
fh = logging.handlers.RotatingFileHandler(log_dir / 'lumber.log', maxBytes=2**16, backupCount=1)

app = Litestar(
    route_handlers=[CountController, get_history],
    state=State({'bag_url': 'http://host.docker.internal/bag/v1.0'}),
    static_files_config=[
        StaticFilesConfig(directories=['app/static'], path='/', html_mode=True)
    ],
    logging_config=logging_config,
    lifespan=[sampling_lifespan],
)

app.logger.addHandler(fh)
