"""GraphML and CSV exporter for OSINT investigation graphs.

Produces output compatible with Gephi, yEd, and Cytoscape. The XML is
built via Python's stdlib ``xml.etree.ElementTree`` — no third-party deps.

Node attributes exported:
    type, value, confidence, source_scanner

Edge attributes exported:
    relation_type, confidence

Usage::

    exporter = GephiExporter()

    # GraphML (Gephi / yEd / Cytoscape)
    xml_str = exporter.export(nodes, edges)

    # CSV pair (Gephi "Import Spreadsheet")
    nodes_csv, edges_csv = exporter.export_to_csv(nodes, edges)
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from typing import Any

import structlog

log = structlog.get_logger()

# GraphML namespace
_GRAPHML_NS = "http://graphml.graphdrawing.org/graphml"

# Attribute key definitions: (key_id, for_element, attr_name, attr_type)
_NODE_KEYS: list[tuple[str, str, str, str]] = [
    ("d_type", "node", "type", "string"),
    ("d_value", "node", "value", "string"),
    ("d_confidence", "node", "confidence", "double"),
    ("d_scanner", "node", "source_scanner", "string"),
]

_EDGE_KEYS: list[tuple[str, str, str, str]] = [
    ("e_relation", "edge", "relation_type", "string"),
    ("e_confidence", "edge", "confidence", "double"),
]


class GephiExporter:
    """Exports an OSINT investigation graph to GraphML or CSV format.

    Both export methods are stateless — every call is independent.
    """

    # ------------------------------------------------------------------
    # GraphML export
    # ------------------------------------------------------------------

    def export(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> str:
        """Serialise the graph to a GraphML XML string.

        Args:
            nodes: List of node dicts with keys id, type, value,
                   confidence, source_scanner.
            edges: List of edge dicts with keys id, from_id, to_id,
                   relation_type, confidence.

        Returns:
            Pretty-printed GraphML XML string (UTF-8 declaration included).
        """
        ET.register_namespace("", _GRAPHML_NS)
        root = ET.Element(f"{{{_GRAPHML_NS}}}graphml")

        # --- Schema: declare all attribute keys ---
        for key_id, for_elem, attr_name, attr_type in _NODE_KEYS + _EDGE_KEYS:
            key_el = ET.SubElement(root, f"{{{_GRAPHML_NS}}}key")
            key_el.set("id", key_id)
            key_el.set("for", for_elem)
            key_el.set("attr.name", attr_name)
            key_el.set("attr.type", attr_type)

        # --- Graph element ---
        graph_el = ET.SubElement(root, f"{{{_GRAPHML_NS}}}graph")
        graph_el.set("id", "G")
        graph_el.set("edgedefault", "directed")

        # --- Nodes ---
        for node in nodes:
            try:
                self._append_node(graph_el, node)
            except Exception as exc:
                log.warning(
                    "GraphML node skipped",
                    node_id=node.get("id"),
                    error=str(exc),
                )

        # --- Edges ---
        for edge in edges:
            try:
                self._append_edge(graph_el, edge)
            except Exception as exc:
                log.warning(
                    "GraphML edge skipped",
                    edge_id=edge.get("id"),
                    error=str(exc),
                )

        log.info(
            "GraphML export complete",
            nodes=len(nodes),
            edges=len(edges),
        )

        # ET.indent is available from Python 3.9+; guard for older envs
        try:
            ET.indent(root, space="  ")
        except AttributeError:
            pass

        xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=False)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes

    def _append_node(
        self,
        graph_el: ET.Element,
        node: dict[str, Any],
    ) -> None:
        """Append a <node> element with its <data> children to the graph."""
        node_el = ET.SubElement(graph_el, f"{{{_GRAPHML_NS}}}node")
        node_el.set("id", str(node["id"]))

        data_map = {
            "d_type": str(node.get("type", "")),
            "d_value": str(node.get("value", "")),
            "d_confidence": str(float(node.get("confidence", 0.0))),
            "d_scanner": str(node.get("source_scanner", "")),
        }
        for key_id, text in data_map.items():
            data_el = ET.SubElement(node_el, f"{{{_GRAPHML_NS}}}data")
            data_el.set("key", key_id)
            data_el.text = text

    def _append_edge(
        self,
        graph_el: ET.Element,
        edge: dict[str, Any],
    ) -> None:
        """Append an <edge> element with its <data> children to the graph."""
        edge_el = ET.SubElement(graph_el, f"{{{_GRAPHML_NS}}}edge")
        edge_el.set("id", str(edge.get("id", f"e-{edge.get('from_id')}-{edge.get('to_id')}")))
        edge_el.set("source", str(edge["from_id"]))
        edge_el.set("target", str(edge["to_id"]))

        data_map = {
            "e_relation": str(edge.get("relation_type", "")),
            "e_confidence": str(float(edge.get("confidence", 0.0))),
        }
        for key_id, text in data_map.items():
            data_el = ET.SubElement(edge_el, f"{{{_GRAPHML_NS}}}data")
            data_el.set("key", key_id)
            data_el.text = text

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    def export_to_csv(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Serialise the graph to a pair of CSV strings for Gephi's importer.

        Gephi's "Import Spreadsheet" expects:
            Nodes CSV: Id, Label, type, confidence, source_scanner
            Edges CSV: Source, Target, Type, relation_type, confidence

        Args:
            nodes: Same schema as ``export()``.
            edges: Same schema as ``export()``.

        Returns:
            (nodes_csv, edges_csv) — two UTF-8 CSV strings.
        """
        nodes_csv = self._build_nodes_csv(nodes)
        edges_csv = self._build_edges_csv(edges)

        log.info(
            "CSV export complete",
            nodes=len(nodes),
            edges=len(edges),
        )
        return nodes_csv, edges_csv

    def _build_nodes_csv(self, nodes: list[dict[str, Any]]) -> str:
        """Build the nodes CSV string."""
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["Id", "Label", "type", "confidence", "source_scanner"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for node in nodes:
            try:
                writer.writerow(
                    {
                        "Id": str(node["id"]),
                        "Label": str(node.get("value", "")),
                        "type": str(node.get("type", "")),
                        "confidence": float(node.get("confidence", 0.0)),
                        "source_scanner": str(node.get("source_scanner", "")),
                    }
                )
            except Exception as exc:
                log.warning("CSV node row skipped", node_id=node.get("id"), error=str(exc))
        return buf.getvalue()

    def _build_edges_csv(self, edges: list[dict[str, Any]]) -> str:
        """Build the edges CSV string."""
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=["Source", "Target", "Type", "relation_type", "confidence"],
            extrasaction="ignore",
        )
        writer.writeheader()
        for edge in edges:
            try:
                writer.writerow(
                    {
                        "Source": str(edge["from_id"]),
                        "Target": str(edge["to_id"]),
                        "Type": "Directed",
                        "relation_type": str(edge.get("relation_type", "")),
                        "confidence": float(edge.get("confidence", 0.0)),
                    }
                )
            except Exception as exc:
                log.warning("CSV edge row skipped", edge=edge, error=str(exc))
        return buf.getvalue()
