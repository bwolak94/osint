from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
import hashlib

router = APIRouter(prefix="/api/v1/social-graph", tags=["social-graph"])

class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # person, organization, location, email, username, phone
    platform: Optional[str]
    connections: int
    risk_score: int

class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str  # follows, connected_to, mentions, member_of, works_at
    weight: float
    platforms: list[str]

class SocialGraphResult(BaseModel):
    seed: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_connections: int
    platforms_covered: list[str]
    depth_reached: int

@router.get("/map", response_model=SocialGraphResult)
async def map_social_graph(target: str, depth: int = 2, platforms: Optional[str] = None):
    """Map the social connections graph for a target"""
    platform_list = platforms.split(",") if platforms else ["Twitter", "LinkedIn", "Instagram", "GitHub", "Reddit"]

    # Generate seed node
    seed_id = hashlib.md5(target.encode()).hexdigest()[:8]
    nodes = [GraphNode(id=seed_id, label=target, type="person", platform=None, connections=random.randint(100, 1000), risk_score=random.randint(10, 80))]
    edges = []

    # Generate connected nodes
    names = ["Alice Johnson", "Bob Smith", "Carol White", "Dave Brown", "Eve Davis", "Frank Miller", "Grace Wilson", "Henry Taylor"]
    for i, name in enumerate(random.sample(names, random.randint(4, 8))):
        node_id = f"node_{i}"
        platform = random.choice(platform_list)
        nodes.append(GraphNode(id=node_id, label=name, type="person", platform=platform, connections=random.randint(10, 500), risk_score=random.randint(5, 60)))
        edges.append(GraphEdge(source=seed_id, target=node_id, relationship=random.choice(["follows", "connected_to", "mentions"]), weight=random.uniform(0.1, 1.0), platforms=[platform]))

    # Add org nodes
    for i, org in enumerate(random.sample(["TechCorp", "SecurityFirm", "OpenSource Project"], random.randint(1, 2))):
        org_id = f"org_{i}"
        nodes.append(GraphNode(id=org_id, label=org, type="organization", platform=None, connections=random.randint(50, 500), risk_score=0))
        edges.append(GraphEdge(source=seed_id, target=org_id, relationship="works_at", weight=0.9, platforms=["LinkedIn"]))

    return SocialGraphResult(
        seed=target,
        nodes=nodes,
        edges=edges,
        total_connections=sum(n.connections for n in nodes),
        platforms_covered=list(set(e.platforms[0] for e in edges if e.platforms)),
        depth_reached=min(depth, 2)
    )
