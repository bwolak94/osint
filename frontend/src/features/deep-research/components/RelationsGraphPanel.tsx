import { useMemo } from 'react'
import ReactFlow, {
  Background,
  MiniMap,
  Controls,
  type Node,
  type Edge,
  ReactFlowProvider,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { Card, CardBody, CardHeader } from '@/shared/components/Card'
import { GitMerge } from 'lucide-react'
import type { RelationsGraph } from '../types'

// Node type → color
const NODE_COLORS: Record<string, string> = {
  person: '#818cf8',
  email: '#34d399',
  phone: '#fbbf24',
  username: '#a78bfa',
  online_service: '#f472b6',
  social_platform: '#f472b6',
}

const nodeColor = (type: string) => NODE_COLORS[type] ?? '#64748b'

interface RelationsGraphPanelProps {
  graph: RelationsGraph
}

function GraphInner({ graph }: RelationsGraphPanelProps) {
  const nodes: Node[] = useMemo(() => {
    const total = graph.nodes.length
    return graph.nodes.map((n, i) => {
      // Radial layout
      const angle = (i / total) * 2 * Math.PI
      const radius = total <= 3 ? 100 : 220
      const x = i === 0 ? 300 : 300 + Math.cos(angle) * radius
      const y = i === 0 ? 200 : 200 + Math.sin(angle) * radius
      const color = nodeColor(n.type)
      return {
        id: n.id,
        type: 'default',
        position: { x, y },
        data: { label: n.label },
        style: {
          background: color + '22',
          border: `2px solid ${color}`,
          borderRadius: '8px',
          color: 'var(--text-primary)',
          fontSize: '12px',
          padding: '6px 10px',
          minWidth: '80px',
          textAlign: 'center' as const,
        },
      }
    })
  }, [graph.nodes])

  const edges: Edge[] = useMemo(() =>
    graph.edges.map((e, i) => ({
      id: `e${i}`,
      source: e.source,
      target: e.target,
      label: e.relation,
      type: 'smoothstep',
      style: { stroke: 'var(--border-default)', strokeWidth: 1.5 },
      labelStyle: { fontSize: 10, fill: 'var(--text-tertiary)' },
      labelBgStyle: { fill: 'var(--bg-elevated)' },
    })),
  [graph.edges])

  return (
    <div style={{ height: 380, background: 'var(--bg-surface)' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodesDraggable
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll
      >
        <Background color="var(--border-subtle)" gap={20} />
        <Controls
          style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-subtle)' }}
        />
        <MiniMap
          nodeColor={(n) => nodeColor(String(n.data?.type ?? 'default'))}
          style={{ background: 'var(--bg-elevated)' }}
        />
      </ReactFlow>
    </div>
  )
}

export function RelationsGraphPanel({ graph }: RelationsGraphPanelProps) {
  if (graph.nodes.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <GitMerge className="h-4 w-4" style={{ color: 'var(--brand-400)' }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Relations Graph
          </span>
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
            {graph.nodes.length} nodes · {graph.edges.length} edges
          </span>
        </div>
      </CardHeader>
      <CardBody style={{ padding: 0, overflow: 'hidden', borderRadius: '0 0 12px 12px' }}>
        <ReactFlowProvider>
          <GraphInner graph={graph} />
        </ReactFlowProvider>
      </CardBody>
    </Card>
  )
}
