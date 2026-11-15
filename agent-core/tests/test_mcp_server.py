import pytest
from agent_core.mcp.server import FighterMCPServer
from agent_core.models.telemetry import MatchSnapshot, PlayerState, Position


def test_mcp_server_tools():
    mcp = FighterMCPServer()

    # Initial state
    assert mcp.get_match_snapshot() == {"status": "WAITING_FOR_MATCH"}

    # Update snapshot
    snapshot = MatchSnapshot(
        frame=50,
        timestamp_ms=1000,
        distance=80.0,
        p1=PlayerState(id=1, pos=Position(x=-20.0, y=0.0)),
        p2=PlayerState(id=2, pos=Position(x=60.0, y=0.0)),
    )
    mcp.update_snapshot(snapshot)

    snap = mcp.get_match_snapshot()
    assert snap["frame"] == 50
    assert snap["p1"]["pos"]["x"] == -20.0

    # Query frame data
    frame_data = mcp.query_frame_data(200)
    assert frame_data["stateno"] == 200
    assert frame_data["data"]["startup"] == 4

    unknown = mcp.query_frame_data(9999)
    assert unknown["status"] == "UNKNOWN_STATENO"

    # Execute macro
    res = mcp.execute_tactical_macro("punish_whiff")
    assert res["status"] == "SUCCESS"

    invalid = mcp.execute_tactical_macro("non_existent")
    assert invalid["status"] == "INVALID_MACRO"
