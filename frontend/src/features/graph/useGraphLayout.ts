import { useCallback } from "react";
import type { Node, Edge } from "reactflow";
import type { LayoutType, OsintNodeData } from "./types";

// Simple force-directed layout (no external dependency)
function forceLayout(nodes: Node<OsintNodeData>[], edges: Edge[]): Node<OsintNodeData>[] {
  if (nodes.length === 0) return nodes;

  const positions = new Map<string, { x: number; y: number }>();
  const centerX = 0;
  const centerY = 0;

  // Initialize positions in a circle
  nodes.forEach((n, i) => {
    const angle = (i / nodes.length) * 2 * Math.PI;
    const radius = Math.min(400, nodes.length * 20);
    positions.set(n.id, {
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    });
  });

  // Simple force simulation (50 iterations)
  const edgeMap = new Map<string, string[]>();
  edges.forEach((e) => {
    if (!edgeMap.has(e.source)) edgeMap.set(e.source, []);
    if (!edgeMap.has(e.target)) edgeMap.set(e.target, []);
    edgeMap.get(e.source)!.push(e.target);
    edgeMap.get(e.target)!.push(e.source);
  });

  for (let iter = 0; iter < 50; iter++) {
    const forces = new Map<string, { fx: number; fy: number }>();
    nodes.forEach((n) => forces.set(n.id, { fx: 0, fy: 0 }));

    // Repulsion between all nodes
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = positions.get(nodes[i].id)!;
        const b = positions.get(nodes[j].id)!;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.max(1, Math.sqrt(dx * dx + dy * dy));
        const repulsion = 5000 / (dist * dist);
        const fa = forces.get(nodes[i].id)!;
        const fb = forces.get(nodes[j].id)!;
        fa.fx -= (dx / dist) * repulsion;
        fa.fy -= (dy / dist) * repulsion;
        fb.fx += (dx / dist) * repulsion;
        fb.fy += (dy / dist) * repulsion;
      }
    }

    // Attraction along edges
    edges.forEach((e) => {
      const a = positions.get(e.source);
      const b = positions.get(e.target);
      if (!a || !b) return;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const attraction = dist * 0.01;
      const fa = forces.get(e.source)!;
      const fb = forces.get(e.target)!;
      fa.fx += (dx / dist) * attraction;
      fa.fy += (dy / dist) * attraction;
      fb.fx -= (dx / dist) * attraction;
      fb.fy -= (dy / dist) * attraction;
    });

    // Apply forces
    const damping = 0.85;
    nodes.forEach((n) => {
      const pos = positions.get(n.id)!;
      const f = forces.get(n.id)!;
      pos.x += f.fx * damping;
      pos.y += f.fy * damping;
    });
  }

  return nodes.map((n) => ({
    ...n,
    position: positions.get(n.id) ?? n.position,
  }));
}

// Hierarchical layout (simple top-to-bottom)
function hierarchicalLayout(nodes: Node<OsintNodeData>[], edges: Edge[]): Node<OsintNodeData>[] {
  if (nodes.length === 0) return nodes;

  // BFS to assign levels
  const adj = new Map<string, string[]>();
  edges.forEach((e) => {
    if (!adj.has(e.source)) adj.set(e.source, []);
    adj.get(e.source)!.push(e.target);
  });

  const levels = new Map<string, number>();
  const visited = new Set<string>();
  const queue: string[] = [];

  // Start from nodes that have no incoming edges
  const hasIncoming = new Set(edges.map((e) => e.target));
  const roots = nodes.filter((n) => !hasIncoming.has(n.id));
  if (roots.length === 0 && nodes.length > 0) roots.push(nodes[0]);

  roots.forEach((r) => {
    levels.set(r.id, 0);
    visited.add(r.id);
    queue.push(r.id);
  });

  while (queue.length > 0) {
    const current = queue.shift()!;
    const currentLevel = levels.get(current) ?? 0;
    (adj.get(current) ?? []).forEach((neighbor) => {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        levels.set(neighbor, currentLevel + 1);
        queue.push(neighbor);
      }
    });
  }

  // Assign unvisited nodes
  nodes.forEach((n) => {
    if (!levels.has(n.id)) levels.set(n.id, 0);
  });

  // Group by level
  const byLevel = new Map<number, string[]>();
  levels.forEach((level, id) => {
    if (!byLevel.has(level)) byLevel.set(level, []);
    byLevel.get(level)!.push(id);
  });

  const xSpacing = 220;
  const ySpacing = 120;

  return nodes.map((n) => {
    const level = levels.get(n.id) ?? 0;
    const siblings = byLevel.get(level) ?? [n.id];
    const index = siblings.indexOf(n.id);
    const totalWidth = (siblings.length - 1) * xSpacing;
    return {
      ...n,
      position: {
        x: -totalWidth / 2 + index * xSpacing,
        y: level * ySpacing,
      },
    };
  });
}

// Circular layout
function circularLayout(nodes: Node<OsintNodeData>[]): Node<OsintNodeData>[] {
  const radius = Math.max(200, nodes.length * 30);
  return nodes.map((n, i) => {
    const angle = (i / nodes.length) * 2 * Math.PI;
    return {
      ...n,
      position: {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
      },
    };
  });
}

// Radial layout - BFS rings from the most connected node
function radialLayout(nodes: Node<OsintNodeData>[], edges: Edge[]): Node<OsintNodeData>[] {
  if (nodes.length === 0) return nodes;

  // Find center node (most connected)
  const degree: Record<string, number> = {};
  edges.forEach((e) => {
    degree[e.source] = (degree[e.source] || 0) + 1;
    degree[e.target] = (degree[e.target] || 0) + 1;
  });

  const centerNode = nodes.reduce((a, b) =>
    (degree[a.id] || 0) >= (degree[b.id] || 0) ? a : b
  );

  // BFS rings from center
  const visited = new Set<string>([centerNode.id]);
  const levels: Map<string, number> = new Map([[centerNode.id, 0]]);
  const queue = [centerNode.id];
  const adj = new Map<string, string[]>();
  edges.forEach((e) => {
    adj.set(e.source, [...(adj.get(e.source) || []), e.target]);
    adj.set(e.target, [...(adj.get(e.target) || []), e.source]);
  });

  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const neighbor of adj.get(current) || []) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        levels.set(neighbor, (levels.get(current) || 0) + 1);
        queue.push(neighbor);
      }
    }
  }

  // Assign disconnected nodes to outermost ring
  const maxLevel = Math.max(0, ...Array.from(levels.values()));
  nodes.forEach((n) => {
    if (!levels.has(n.id)) {
      levels.set(n.id, maxLevel + 1);
    }
  });

  // Position by ring
  const byLevel = new Map<number, string[]>();
  levels.forEach((level, id) => {
    if (!byLevel.has(level)) byLevel.set(level, []);
    byLevel.get(level)!.push(id);
  });

  const ringSpacing = 180;
  return nodes.map((n) => {
    const level = levels.get(n.id) ?? 0;
    if (level === 0) return { ...n, position: { x: 0, y: 0 } };
    const ring = byLevel.get(level) || [];
    const idx = ring.indexOf(n.id);
    const angle = (idx / ring.length) * 2 * Math.PI;
    const radius = level * ringSpacing;
    return { ...n, position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius } };
  });
}

// Block layout - groups nodes by type in columns
function blockLayout(nodes: Node<OsintNodeData>[]): Node<OsintNodeData>[] {
  if (nodes.length === 0) return nodes;

  // Group nodes by type
  const groups = new Map<string, Node<OsintNodeData>[]>();
  nodes.forEach((n) => {
    const type = n.data.type;
    if (!groups.has(type)) groups.set(type, []);
    groups.get(type)!.push(n);
  });

  const columnWidth = 250;
  const rowHeight = 80;
  const headerHeight = 30;
  const result: Node<OsintNodeData>[] = [];

  let colIndex = 0;
  groups.forEach((groupNodes) => {
    const x = colIndex * columnWidth;
    groupNodes.forEach((n, rowIndex) => {
      result.push({
        ...n,
        position: {
          x,
          y: headerHeight + rowIndex * rowHeight,
        },
      });
    });
    colIndex++;
  });

  return result;
}

export function useGraphLayout() {
  const applyLayout = useCallback(
    (nodes: Node<OsintNodeData>[], edges: Edge[], layout: LayoutType): Node<OsintNodeData>[] => {
      switch (layout) {
        case "force":
          return forceLayout(nodes, edges);
        case "hierarchical":
          return hierarchicalLayout(nodes, edges);
        case "circular":
          return circularLayout(nodes);
        case "radial":
          return radialLayout(nodes, edges);
        case "block":
          return blockLayout(nodes);
        case "manual":
        default:
          return nodes;
      }
    },
    [],
  );

  return { applyLayout };
}
