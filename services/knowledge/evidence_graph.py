from typing import Dict, List, Any, Set, Optional
from collections import defaultdict
from .evidence import ResearchEvidence
from services.models.research_models import Finding

class Node:
    def __init__(self, node_id: str, node_type: str, data: Any):
        self.node_id = node_id
        self.node_type = node_type  # 'entity', 'evidence', 'finding'
        self.data = data
        self.confidence: float = getattr(data, 'confidence', 0.5) if hasattr(data, 'confidence') else 1.0

class Edge:
    def __init__(self, source_id: str, target_id: str, relationship: str, weight: float = 1.0):
        self.source_id = source_id
        self.target_id = target_id
        self.relationship = relationship  # 'SUPPORTS', 'CONFLICTS_WITH', 'RELATES_TO'
        self.weight = weight

class EvidenceGraph:
    """
    A Directed Graph mapping Entities -> Evidence -> Findings.
    Supports confidence propagation and conflict tracking.
    """
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self._adj_list: Dict[str, List[Edge]] = defaultdict(list)
        self._rev_adj_list: Dict[str, List[Edge]] = defaultdict(list)

    def add_node(self, node: Node):
        self.nodes[node.node_id] = node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
        self._adj_list[edge.source_id].append(edge)
        self._rev_adj_list[edge.target_id].append(edge)

    def add_evidence(self, entity_id: str, evidence: ResearchEvidence):
        if entity_id not in self.nodes:
            self.add_node(Node(entity_id, "entity", {"name": entity_id}))
            
        ev_node = Node(evidence.id, "evidence", evidence)
        self.add_node(ev_node)
        self.add_edge(Edge(entity_id, evidence.id, "RELATES_TO"))

    def add_finding(self, finding: Finding):
        f_node = Node(finding.id, "finding", finding)
        self.add_node(f_node)
        
        for ev_id in finding.evidence_refs:
            if ev_id in self.nodes:
                self.add_edge(Edge(ev_id, finding.id, "SUPPORTS"))

    def register_conflict(self, node_id_1: str, node_id_2: str):
        self.add_edge(Edge(node_id_1, node_id_2, "CONFLICTS_WITH", weight=-1.0))
        self.add_edge(Edge(node_id_2, node_id_1, "CONFLICTS_WITH", weight=-1.0))

    def propagate_confidence(self):
        """
        Updates the confidence of finding nodes based on the supporting evidence nodes.
        If conflicting evidence is found, confidence is reduced.
        """
        for node_id, node in self.nodes.items():
            if node.node_type == "finding":
                supporting_edges = [e for e in self._rev_adj_list[node_id] if e.relationship == "SUPPORTS"]
                if not supporting_edges:
                    continue
                    
                total_conf = 0.0
                for e in supporting_edges:
                    source_node = self.nodes.get(e.source_id)
                    if source_node:
                        # Check if this source has conflicts
                        conflicts = [ce for ce in self._adj_list[source_node.node_id] if ce.relationship == "CONFLICTS_WITH"]
                        penalty = 0.2 if conflicts else 0.0
                        total_conf += max(0.0, source_node.confidence - penalty)
                        
                avg_conf = total_conf / len(supporting_edges)
                node.confidence = avg_conf
                node.data.confidence = avg_conf

    def get_subgraph_for_entity(self, entity_id: str) -> Dict[str, Any]:
        """
        Extracts a dictionary view of the graph for a specific entity.
        """
        if entity_id not in self.nodes:
            return {}
            
        result = {"entity": self.nodes[entity_id].data, "evidence": [], "findings": []}
        
        evidence_edges = self._adj_list.get(entity_id, [])
        ev_ids = set()
        
        for e in evidence_edges:
            if e.relationship == "RELATES_TO" and self.nodes[e.target_id].node_type == "evidence":
                ev_node = self.nodes[e.target_id]
                ev_ids.add(ev_node.node_id)
                result["evidence"].append({
                    "id": ev_node.node_id,
                    "value": ev_node.data.value,
                    "confidence": ev_node.confidence
                })
                
        # Find all findings supported by this evidence
        finding_ids = set()
        for ev_id in ev_ids:
            edges = self._adj_list.get(ev_id, [])
            for e in edges:
                if e.relationship == "SUPPORTS" and self.nodes[e.target_id].node_type == "finding":
                    finding_ids.add(e.target_id)
                    
        for f_id in finding_ids:
            f_node = self.nodes[f_id]
            result["findings"].append({
                "id": f_node.node_id,
                "description": f_node.data.description,
                "confidence": f_node.confidence
            })
            
        return result
