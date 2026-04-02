import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
  type Node,
  type Edge,
  type NodeTypes,
  type OnNodeDrag,
} from "@xyflow/react";
import dagre from "dagre";
import "@xyflow/react/dist/style.css";

import { api, DagNode, DagEdge } from "../api";
import { socket } from "../socket";
import JobNode from "./JobNode";
import FlowDetailPanel from "./FlowDetailPanel";

const NODE_WIDTH = 260;
const NODE_HEIGHT = 72;

const nodeTypes: NodeTypes = {
  jobNode: JobNode,
};

function getStatusColor(status: string): string {
  switch (status) {
    case "running":
      return "#38a063";
    case "done":
      return "#4caf7d";
    case "failed":
      return "#c0392b";
    case "cancelled":
      return "#4a6450";
    case "queued":
      return "#5a6b5a";
    default:
      return "#5a6b5a";
  }
}

function layoutGraph(
  dagNodes: DagNode[],
  dagEdges: DagEdge[]
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 80, marginx: 40, marginy: 40 });

  dagNodes.forEach((n) => {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  });

  dagEdges.forEach((e) => {
    g.setEdge(e.source, e.target);
  });

  dagre.layout(g);

  const nodes: Node[] = dagNodes.map((n) => {
    const pos = g.node(n.id);
    return {
      id: n.id,
      type: "jobNode",
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
      data: {
        title: n.title,
        status: n.status,
        model: n.model,
      },
    };
  });

  const edges: Edge[] = dagEdges.map((e, i) => {
    const targetNode = dagNodes.find((n) => n.id === e.target);
    const sourceNode = dagNodes.find((n) => n.id === e.source);
    const isRunning = targetNode?.status === "running";
    const isFailed = sourceNode?.status === "failed";

    return {
      id: `e-${i}`,
      source: e.source,
      target: e.target,
      animated: isRunning,
      style: {
        stroke: isFailed ? "#c0392b" : isRunning ? "#38a063" : "#4a6450",
        strokeWidth: 2,
      },
    };
  });

  return { nodes, edges };
}

interface Props {
  selectedProject: string | null;
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function AgentFlowView({ selectedProject, onCancel, onDelete }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[]);
  const [dagData, setDagData] = useState<{ nodes: DagNode[]; edges: DagEdge[] }>({
    nodes: [],
    edges: [],
  });
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const loadDag = useCallback(async () => {
    const data = await api.jobs.dag(selectedProject || undefined);
    setDagData(data);
    const { nodes: layoutNodes, edges: layoutEdges } = layoutGraph(data.nodes, data.edges);
    setNodes(layoutNodes);
    setEdges(layoutEdges);
  }, [selectedProject, setNodes, setEdges]);

  // Initial load
  useEffect(() => {
    loadDag();
  }, [loadDag]);

  // Real-time updates
  useEffect(() => {
    function onJobUpdated(data: { id: string; status: string }) {
      setDagData((prev) => {
        const updated = {
          ...prev,
          nodes: prev.nodes.map((n) =>
            n.id === data.id ? { ...n, status: data.status } : n
          ),
        };
        const { nodes: ln, edges: le } = layoutGraph(updated.nodes, updated.edges);
        setNodes(ln);
        setEdges(le);
        return updated;
      });
    }

    socket.on("job:updated", onJobUpdated);
    return () => {
      socket.off("job:updated", onJobUpdated);
    };
  }, [setNodes, setEdges]);

  // Poll for new jobs (they may be created outside this view)
  useEffect(() => {
    const interval = setInterval(loadDag, 10000);
    return () => clearInterval(interval);
  }, [loadDag]);

  const selectedNode = useMemo(
    () => dagData.nodes.find((n) => n.id === selectedNodeId) || null,
    [dagData.nodes, selectedNodeId]
  );

  const upstreamIds = useMemo(
    () =>
      selectedNodeId
        ? dagData.edges.filter((e) => e.target === selectedNodeId).map((e) => e.source)
        : [],
    [dagData.edges, selectedNodeId]
  );

  const downstreamIds = useMemo(
    () =>
      selectedNodeId
        ? dagData.edges.filter((e) => e.source === selectedNodeId).map((e) => e.target)
        : [],
    [dagData.edges, selectedNodeId]
  );

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNodeId(node.id);
  }, []);

  const handleCancel = useCallback(
    (id: string) => {
      onCancel(id);
      setTimeout(loadDag, 500);
    },
    [onCancel, loadDag]
  );

  const handleDelete = useCallback(
    (id: string) => {
      setSelectedNodeId(null);
      onDelete(id);
      setTimeout(loadDag, 500);
    },
    [onDelete, loadDag]
  );

  return (
    <div className="agentflow-container">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#253027" />
        <Controls
          className="flow-controls"
          showInteractive={false}
        />
        <MiniMap
          className="flow-minimap"
          nodeColor={(n) => getStatusColor((n.data as { status?: string })?.status || "queued")}
          maskColor="rgba(10, 15, 11, 0.8)"
        />
      </ReactFlow>

      {dagData.nodes.length === 0 && (
        <div className="flow-empty-overlay">
          <div className="empty-state">
            <h2>No jobs yet</h2>
            <p>Create jobs with dependencies to see the flow graph</p>
          </div>
        </div>
      )}

      {selectedNode && (
        <FlowDetailPanel
          node={selectedNode}
          allNodes={dagData.nodes}
          upstreamIds={upstreamIds}
          downstreamIds={downstreamIds}
          onClose={() => setSelectedNodeId(null)}
          onCancel={handleCancel}
          onDelete={handleDelete}
          onNodeSelect={(id) => setSelectedNodeId(id)}
        />
      )}
    </div>
  );
}
