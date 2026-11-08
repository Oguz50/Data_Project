import networkx as nx
from networkx.algorithms import bipartite
from connect_databricks import query

# Nur abgeschlossene Bestellungen berücksichtigen.
rows = query("""
    SELECT DISTINCT
        o.customer_id,
        p.product_id,
        p.product_name
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE o.order_status = 'completed'
""")

graph = nx.Graph()

for row in rows:
    customer = f"customer:{row['customer_id']}"
    product = f"product:{row['product_id']}"

    graph.add_node(customer, type="Customer", bipartite=0)
    graph.add_node(
        product,
        type="Product",
        bipartite=1,
        name=row["product_name"],
    )
    graph.add_edge(customer, product, relation="PURCHASED")

# Produkte verbinden, wenn sie mindestens einen Käufer gemeinsam haben.
products = [
    node for node, data in graph.nodes(data=True)
    if data["type"] == "Product"
]

product_graph = bipartite.weighted_projected_graph(graph, products)

pairs = sorted(
    product_graph.edges(data=True),
    key=lambda edge: edge[2]["weight"],
    reverse=True,
)

for first, second, data in pairs[:10]:
    print(
        graph.nodes[first]["name"],
        "↔",
        graph.nodes[second]["name"],
        f"({data['weight']} gemeinsame Käufer)",
    )