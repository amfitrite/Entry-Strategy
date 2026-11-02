"""Tests for Port 5558 TCP Bridge Server."""
import socket
import time
from entrystrategy.data.mt5_bridge import MT5BridgeServer
from entrystrategy.core.models import TickData, Candle


def test_bridge_tcp_socket_communication():
    received_ticks = []

    def on_tick_cb(t: TickData):
        received_ticks.append(t)

    test_port = 5568
    server = MT5BridgeServer(
        host="127.0.0.1",
        port=test_port,
        on_tick=on_tick_cb,
    )
    server.start()
    time.sleep(0.15)  # Allow socket to bind

    # Connect client
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", test_port))

    # Send symbol and ticks
    now_ms = int(time.time() * 1000)
    data = (
        "#SYMBOL:XAUUSD\n"
        f"{now_ms},2745.10,2745.30,2745.20,1.0,0\n"
        f"{now_ms + 100},2745.15,2745.35,2745.25,2.0,0\n"
    )
    client.sendall(data.encode("utf-8"))
    time.sleep(0.2)

    client.close()
    server.stop()

    assert server.total_ticks >= 2
    assert len(received_ticks) >= 2
    assert received_ticks[0].symbol == "XAUUSD"
    assert received_ticks[0].bid == 2745.10
    assert received_ticks[1].ask == 2745.35
