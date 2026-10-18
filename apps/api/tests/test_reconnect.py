"""A new FalkorDB connection sees assertions written earlier."""

from falkordb import FalkorDB

from faultline.graph.names import graph_name_for_tenant


def test_second_connection_sees_seeded_assertion(settings, seeded):
    kwargs = {
        "host": settings.falkordb_host,
        "port": settings.falkordb_port,
        "socket_timeout": 2,
        "socket_connect_timeout": 2,
    }
    if settings.falkordb_password:
        kwargs["password"] = settings.falkordb_password
    database = FalkorDB(**kwargs)
    graph = database.select_graph(graph_name_for_tenant("tenant-synthetic"))
    result = graph.query(
        "MATCH (a:Assertion {id: $id}) RETURN a.value, a.status",
        {"id": "assert-region-b"},
    )
    assert result.result_set[0][0] == "region-b"
    assert result.result_set[0][1] == "current"
