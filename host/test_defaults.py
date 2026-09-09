from defaults import WS_PORT


def test_ws_port_is_not_8000():
    assert WS_PORT == 15151
    assert WS_PORT != 8000
