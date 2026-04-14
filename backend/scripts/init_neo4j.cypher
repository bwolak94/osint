// Create constraints for node uniqueness
CREATE CONSTRAINT osint_node_unique IF NOT EXISTS
FOR (n:OsintNode) REQUIRE (n.investigation_id, n.node_type, n.label_normalized) IS UNIQUE;

// Create indexes for common query patterns
CREATE INDEX osint_node_investigation IF NOT EXISTS
FOR (n:OsintNode) ON (n.investigation_id);

CREATE INDEX osint_node_type IF NOT EXISTS
FOR (n:OsintNode) ON (n.node_type);

CREATE INDEX osint_node_id IF NOT EXISTS
FOR (n:OsintNode) ON (n.id);
