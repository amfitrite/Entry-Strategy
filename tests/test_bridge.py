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


def test_bridge_null_byte_resilience():
    """Verify bridge strips MQL5 null bytes cleanly without ValueError."""
    received = []

    def on_tick_cb(t: TickData, is_history: bool = False):
        received.append((t, is_history))

    test_port = 5569
    server = MT5BridgeServer(host="127.0.0.1", port=test_port, on_tick=on_tick_cb)
    server.start()
    time.sleep(0.15)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", test_port))

    now_ms = int(time.time() * 1000)
    # Simulate MQL5 StringToCharArray null-byte append
    dirty_data = (
        f"\x00#SYMBOL:XAUUSDc\x00\n"
        f"\x00{now_ms},3964.10,3964.30,3964.20,1.5,6\x00\n"
        f"TICK|{now_ms + 50},3964.15,3964.35,3964.25,2.0,6\n"
    )
    client.sendall(dirty_data.encode("utf-8"))
    time.sleep(0.2)

    client.close()
    server.stop()

    assert len(received) == 2
    t1, is_hist1 = received[0]
    assert t1.symbol == "XAUUSDc"
    assert t1.bid == 3964.10
    assert is_hist1 is False

    t2, is_hist2 = received[1]
    assert t2.bid == 3964.15


def test_bridge_history_tick_detection():
    """Verify ticks older than 15s are marked is_history=True."""
    received = []

    def on_tick_cb(t: TickData, is_history: bool = False):
        received.append((t, is_history))

    test_port = 5570
    server = MT5BridgeServer(host="127.0.0.1", port=test_port, on_tick=on_tick_cb)
    server.start()
    time.sleep(0.15)

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", test_port))

    now_ms = int(time.time() * 1000)
    old_ms = now_ms - 60000  # 1 minute ago (history)
    data = (
        f"{old_ms},2740.00,2740.20,2740.10,1.0,0\n"
        f"{now_ms},2745.00,2745.20,2745.10,1.0,0\n"
    )
    client.sendall(data.encode("utf-8"))
    time.sleep(0.2)

    client.close()
    server.stop()

    assert len(received) == 2
    assert received[0][1] is True   # old tick marked is_history=True
    assert received[1][1] is False  # real-time tick marked is_history=False
