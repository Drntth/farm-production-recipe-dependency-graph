"""
Export a production dependency graph to GraphML.

Writes a **yEd-compatible** GraphML file that includes:

- standard GraphML ``<data>`` attributes (kind, name, type, weight, …)
- yFiles node/edge graphics with **visible labels** on the canvas

This way yEd Live and yEd Desktop show readable text on every node
(e.g. ``Milk ← cow_pasture [resource]``) without needing the Properties
Mapper.  Gephi and Cytoscape ignore the yFiles extensions and still
read all standard attributes.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

import networkx as nx

from .labels import edge_label, node_label

_NS_GRAPHML = "http://graphml.graphdrawing.org/xmlns"
_NS_Y = "http://www.yworks.com/xml/graphml"
_NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("", _NS_GRAPHML)
ET.register_namespace("y", _NS_Y)
ET.register_namespace("xsi", _NS_XSI)


def export_graphml(G: nx.DiGraph, path: Path | str) -> Path:
    """
    Write *G* to a yEd-compatible GraphML file at *path*.

    Returns the resolved Path of the written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element(
        f"{{{_NS_GRAPHML}}}graphml",
        {
            f"{{{_NS_XSI}}}schemaLocation": (
                "http://graphml.graphdrawing.org/xmlns "
                "http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd"
            ),
        },
    )

    # --- key declarations -------------------------------------------------
    ET.SubElement(
        root,
        f"{{{_NS_GRAPHML}}}key",
        {"id": "d_node_graphics", "for": "node", "yfiles.type": "nodegraphics"},
    )
    ET.SubElement(
        root,
        f"{{{_NS_GRAPHML}}}key",
        {"id": "d_edge_graphics", "for": "edge", "yfiles.type": "edgegraphics"},
    )

    node_attr_keys = [
        ("kind", "string"),
        ("id", "string"),
        ("name", "string"),
        ("type", "string"),
        ("unlock_level", "long"),
        ("source_location_id", "string"),
        ("label", "string"),
    ]
    for i, (name, atype) in enumerate(node_attr_keys):
        ET.SubElement(
            root,
            f"{{{_NS_GRAPHML}}}key",
            {
                "id": f"dn_{i}",
                "for": "node",
                "attr.name": name,
                "attr.type": atype,
            },
        )

    edge_attr_keys = [
        ("edge_type", "string"),
        ("weight", "double"),
        ("amount", "long"),
        ("recipe_id", "string"),
        ("ratio", "double"),
        ("label", "string"),
    ]
    for i, (name, atype) in enumerate(edge_attr_keys):
        ET.SubElement(
            root,
            f"{{{_NS_GRAPHML}}}key",
            {
                "id": f"de_{i}",
                "for": "edge",
                "attr.name": name,
                "attr.type": atype,
            },
        )

    graph_el = ET.SubElement(
        root,
        f"{{{_NS_GRAPHML}}}graph",
        {"id": "G", "edgedefault": "directed"},
    )

    # --- nodes ------------------------------------------------------------
    node_key_index = {name: f"dn_{i}" for i, (name, _) in enumerate(node_attr_keys)}

    for node_id, attrs in G.nodes(data=True):
        label = node_label(node_id, attrs)
        kind = attrs.get("kind", "")

        node_el = ET.SubElement(
            graph_el, f"{{{_NS_GRAPHML}}}node", {"id": str(node_id)}
        )

        graphics_data = ET.SubElement(
            node_el, f"{{{_NS_GRAPHML}}}data", {"key": "d_node_graphics"}
        )
        shape = ET.SubElement(graphics_data, f"{{{_NS_Y}}}ShapeNode")
        ET.SubElement(
            shape,
            f"{{{_NS_Y}}}Geometry",
            {"height": "40", "width": "120", "x": "0", "y": "0"},
        )

        fill_color = "#4C78A8" if kind == "location" else "#F58518"
        ET.SubElement(
            shape,
            f"{{{_NS_Y}}}Fill",
            {"color": fill_color, "transparent": "false"},
        )
        ET.SubElement(
            shape,
            f"{{{_NS_Y}}}BorderStyle",
            {"color": "#333333", "type": "line", "width": "1.0"},
        )
        node_label_el = ET.SubElement(
            shape,
            f"{{{_NS_Y}}}NodeLabel",
            {
                "alignment": "center",
                "autoSizePolicy": "content",
                "fontFamily": "Dialog",
                "fontSize": "11",
                "fontStyle": "plain",
                "textColor": "#000000",
            },
        )
        node_label_el.text = label
        ET.SubElement(shape, f"{{{_NS_Y}}}Shape", {"type": "roundrectangle"})

        export_attrs = {
            "kind": attrs.get("kind"),
            "id": node_id,
            "name": attrs.get("name"),
            "type": attrs.get("type"),
            "unlock_level": attrs.get("unlock_level"),
            "source_location_id": attrs.get("source_location_id"),
            "label": label,
        }
        for name, value in export_attrs.items():
            if value is None or value == "":
                continue
            data_el = ET.SubElement(
                node_el, f"{{{_NS_GRAPHML}}}data", {"key": node_key_index[name]}
            )
            data_el.text = str(value)

    # --- edges ------------------------------------------------------------
    edge_key_index = {name: f"de_{i}" for i, (name, _) in enumerate(edge_attr_keys)}

    for idx, (u, v, attrs) in enumerate(G.edges(data=True)):
        elabel = edge_label(attrs)

        edge_el = ET.SubElement(
            graph_el,
            f"{{{_NS_GRAPHML}}}edge",
            {"id": f"e{idx}", "source": str(u), "target": str(v)},
        )

        graphics_data = ET.SubElement(
            edge_el, f"{{{_NS_GRAPHML}}}data", {"key": "d_edge_graphics"}
        )
        poly = ET.SubElement(graphics_data, f"{{{_NS_Y}}}PolyLineEdge")
        ET.SubElement(
            poly,
            f"{{{_NS_Y}}}LineStyle",
            {"color": "#A0A0A0", "type": "line", "width": "1.0"},
        )
        ET.SubElement(
            poly, f"{{{_NS_Y}}}Arrows", {"source": "none", "target": "standard"}
        )
        if elabel:
            edge_label_el = ET.SubElement(
                poly,
                f"{{{_NS_Y}}}EdgeLabel",
                {
                    "alignment": "center",
                    "fontFamily": "Dialog",
                    "fontSize": "9",
                    "fontStyle": "plain",
                    "textColor": "#D0D0D0",
                    "backgroundColor": "#2A2A2A",
                },
            )
            edge_label_el.text = elabel

        export_attrs = {
            "edge_type": attrs.get("edge_type"),
            "weight": attrs.get("weight"),
            "amount": attrs.get("amount"),
            "recipe_id": attrs.get("recipe_id"),
            "ratio": attrs.get("ratio"),
            "label": elabel or None,
        }
        for name, value in export_attrs.items():
            if value is None or value == "":
                continue
            data_el = ET.SubElement(
                edge_el, f"{{{_NS_GRAPHML}}}data", {"key": edge_key_index[name]}
            )
            data_el.text = str(value)

    rough = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(rough)
    pretty = parsed.toprettyxml(indent="  ", encoding="utf-8")

    path.write_bytes(pretty)
    return path.resolve()
