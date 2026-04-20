import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Test graph types
import type { OsintNodeData, OsintEdgeData, NodeType, LayoutType } from "../types";

// Test layout algorithms
import { useGraphLayout } from "../useGraphLayout";
import { renderHook } from "@testing-library/react";
import type { Node, Edge } from "reactflow";

// Helper to create mock node data
function mockNodeData(overrides: Partial<OsintNodeData> = {}): OsintNodeData {
  return {
    id: "n1",
    type: "person",
    label: "John Doe",
    confidence: 0.85,
    sources: ["holehe"],
    properties: {},
    isSelected: false,
    isDimmed: false,
    isOnPath: false,
    ...overrides,
  };
}

function mockNode(id: string, type: NodeType = "person", label: string = "Node"): Node<OsintNodeData> {
  return {
    id,
    type,
    position: { x: 0, y: 0 },
    data: mockNodeData({ id, type, label }),
  };
}

function mockEdge(id: string, source: string, target: string): Edge<OsintEdgeData> {
  return {
    id,
    source,
    target,
    type: "relationship",
    data: {
      label: "CONNECTED_TO",
      relationType: "connected_to",
      confidence: 0.7,
      isOnPath: false,
    },
  };
}

// ============== Types ==============
describe("Graph Types", () => {
  it("OsintNodeData has all required fields", () => {
    const data = mockNodeData();
    expect(data.id).toBe("n1");
    expect(data.type).toBe("person");
    expect(data.confidence).toBe(0.85);
    expect(data.isDimmed).toBe(false);
    expect(data.isOnPath).toBe(false);
  });

  it("supports all node types", () => {
    const types: NodeType[] = ["person", "company", "email", "phone", "username", "ip", "domain"];
    types.forEach((t) => {
      const data = mockNodeData({ type: t });
      expect(data.type).toBe(t);
    });
  });
});

// ============== Layout ==============
describe("useGraphLayout", () => {
  it("force layout positions nodes", () => {
    const { result } = renderHook(() => useGraphLayout());
    const nodes = [mockNode("a"), mockNode("b"), mockNode("c")];
    const edges = [mockEdge("e1", "a", "b"), mockEdge("e2", "b", "c")];

    const laid = result.current.applyLayout(nodes, edges, "force");
    expect(laid).toHaveLength(3);
    // Nodes should have different positions
    const positions = laid.map((n) => `${Math.round(n.position.x)},${Math.round(n.position.y)}`);
    const unique = new Set(positions);
    expect(unique.size).toBeGreaterThan(1);
  });

  it("hierarchical layout assigns levels", () => {
    const { result } = renderHook(() => useGraphLayout());
    const nodes = [mockNode("root"), mockNode("child1"), mockNode("child2")];
    const edges = [mockEdge("e1", "root", "child1"), mockEdge("e2", "root", "child2")];

    const laid = result.current.applyLayout(nodes, edges, "hierarchical");
    // Root should be above children (smaller y)
    const rootY = laid.find((n) => n.id === "root")!.position.y;
    const child1Y = laid.find((n) => n.id === "child1")!.position.y;
    expect(rootY).toBeLessThan(child1Y);
  });

  it("circular layout places nodes on circle", () => {
    const { result } = renderHook(() => useGraphLayout());
    const nodes = [mockNode("a"), mockNode("b"), mockNode("c"), mockNode("d")];

    const laid = result.current.applyLayout(nodes, [], "circular");
    // All nodes should be at roughly the same distance from center
    const distances = laid.map((n) =>
      Math.sqrt(n.position.x ** 2 + n.position.y ** 2),
    );
    const avgDist = distances.reduce((a, b) => a + b) / distances.length;
    distances.forEach((d) => {
      expect(Math.abs(d - avgDist)).toBeLessThan(1); // All on same circle
    });
  });

  it("manual layout returns nodes unchanged", () => {
    const { result } = renderHook(() => useGraphLayout());
    const nodes = [
      { ...mockNode("a"), position: { x: 10, y: 20 } },
      { ...mockNode("b"), position: { x: 30, y: 40 } },
    ];

    const laid = result.current.applyLayout(nodes, [], "manual");
    expect(laid[0].position).toEqual({ x: 10, y: 20 });
    expect(laid[1].position).toEqual({ x: 30, y: 40 });
  });

  it("empty nodes returns empty array", () => {
    const { result } = renderHook(() => useGraphLayout());
    const laid = result.current.applyLayout([], [], "force");
    expect(laid).toEqual([]);
  });

  it("single node force layout", () => {
    const { result } = renderHook(() => useGraphLayout());
    const laid = result.current.applyLayout([mockNode("solo")], [], "force");
    expect(laid).toHaveLength(1);
  });
});

// ============== Node Search ==============
describe("Node Search Logic", () => {
  it("search matches case insensitive", () => {
    const node = mockNodeData({ label: "Jan Kowalski" });
    expect(node.label.toLowerCase().includes("jan")).toBe(true);
    expect(node.label.toLowerCase().includes("kowalski")).toBe(true);
    expect(node.label.toLowerCase().includes("xyz")).toBe(false);
  });
});

// ============== Node Filters ==============
describe("Node Filters", () => {
  it("filters by type", () => {
    const nodes = [
      mockNode("1", "person", "Alice"),
      mockNode("2", "email", "a@b.com"),
      mockNode("3", "company", "Corp"),
    ];
    const visibleTypes = new Set<NodeType>(["person", "company"]);
    const filtered = nodes.filter((n) => visibleTypes.has(n.data.type));
    expect(filtered).toHaveLength(2);
    expect(filtered.map((n) => n.data.type)).toEqual(["person", "company"]);
  });

  it("filters by confidence", () => {
    const nodes = [
      mockNode("1", "person", "High"),
      mockNode("2", "email", "Low"),
    ];
    nodes[0].data.confidence = 0.9;
    nodes[1].data.confidence = 0.2;

    const minConfidence = 0.5;
    const filtered = nodes.filter((n) => n.data.confidence >= minConfidence);
    expect(filtered).toHaveLength(1);
    expect(filtered[0].data.label).toBe("High");
  });

  it("combined type + confidence filter", () => {
    const nodes = [
      { ...mockNode("1", "person", "A"), data: { ...mockNodeData({ type: "person", confidence: 0.9 }) } },
      { ...mockNode("2", "person", "B"), data: { ...mockNodeData({ type: "person", confidence: 0.2 }) } },
      { ...mockNode("3", "email", "C"), data: { ...mockNodeData({ type: "email", confidence: 0.8 }) } },
    ];
    const visibleTypes = new Set<NodeType>(["person"]);
    const minConfidence = 0.5;
    const filtered = nodes.filter((n) => visibleTypes.has(n.data.type) && n.data.confidence >= minConfidence);
    expect(filtered).toHaveLength(1);
  });
});

// ============== Edge Rendering Logic ==============
describe("Edge Style Logic", () => {
  function getStrokeWidth(confidence: number): number {
    if (confidence >= 0.9) return 3;
    if (confidence >= 0.6) return 2;
    return 1;
  }

  function getStrokeDash(confidence: number): string | undefined {
    if (confidence >= 0.6) return undefined;
    if (confidence >= 0.3) return "6 3";
    return "2 2";
  }

  it("high confidence gets thick solid line", () => {
    expect(getStrokeWidth(0.95)).toBe(3);
    expect(getStrokeDash(0.95)).toBeUndefined();
  });

  it("medium confidence gets medium dashed line", () => {
    expect(getStrokeWidth(0.5)).toBe(1);
    expect(getStrokeDash(0.5)).toBe("6 3");
  });

  it("low confidence gets thin dotted line", () => {
    expect(getStrokeWidth(0.1)).toBe(1);
    expect(getStrokeDash(0.1)).toBe("2 2");
  });
});

// ============== Path Finding Logic ==============
describe("Path Finding", () => {
  it("path nodes are highlighted", () => {
    const pathNodeIds = new Set(["a", "c", "e"]);
    const nodes = [
      mockNode("a"), mockNode("b"), mockNode("c"),
      mockNode("d"), mockNode("e"),
    ];
    const highlighted = nodes.map((n) => ({
      ...n,
      data: { ...n.data, isOnPath: pathNodeIds.has(n.id), isDimmed: !pathNodeIds.has(n.id) },
    }));

    expect(highlighted.filter((n) => n.data.isOnPath)).toHaveLength(3);
    expect(highlighted.filter((n) => n.data.isDimmed)).toHaveLength(2);
  });
});
