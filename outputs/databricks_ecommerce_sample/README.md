# Databricks E-Commerce Beispieldaten

Enthalten sind vier synthetische, relational verknüpfte CSV-Dateien:

- `customers.csv`: 100 Kunden
- `products.csv`: 50 Produkte
- `orders.csv`: 300 Bestellungen
- `order_items.csv`: 904 Bestellpositionen

## Beziehungen

- `orders.customer_id → customers.customer_id`
- `order_items.order_id → orders.order_id`
- `order_items.product_id → products.product_id`

## Verwendung

1. Lade die vier CSV-Dateien in einen Databricks-Ordner oder ein Unity-Catalog-Volume.
2. Importiere `load_to_databricks.py` als Notebook.
3. Setze das Widget `base_path` auf den Ablageort und führe alle Zellen aus.

Datumsfelder verwenden ISO 8601. Beträge sind in EUR. Alle Personen und Transaktionen sind fiktiv.
