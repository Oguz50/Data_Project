# Databricks notebook source
# COMMAND ----------
# Passe base_path an den Zielordner in DBFS, Volumes oder Cloud Storage an.
dbutils.widgets.text("base_path", "/Volumes/main/default/ecommerce_sample")
base_path = dbutils.widgets.get("base_path").rstrip("/")

from pyspark.sql.types import (
    StructType, StructField, StringType, DateType, TimestampType,
    DecimalType, IntegerType, BooleanType
)

schemas = {
    "customers": StructType([
        StructField("customer_id", StringType(), False), StructField("first_name", StringType()),
        StructField("last_name", StringType()), StructField("email", StringType()),
        StructField("city", StringType()), StructField("state", StringType()),
        StructField("postal_code", StringType()), StructField("country_code", StringType()),
        StructField("signup_date", DateType()), StructField("marketing_channel", StringType()),
        StructField("loyalty_tier", StringType()), StructField("is_active", BooleanType())
    ]),
    "products": StructType([
        StructField("product_id", StringType(), False), StructField("sku", StringType()),
        StructField("product_name", StringType()), StructField("category", StringType()),
        StructField("brand", StringType()), StructField("unit_price_eur", DecimalType(10, 2)),
        StructField("unit_cost_eur", DecimalType(10, 2)), StructField("stock_quantity", IntegerType()),
        StructField("is_discontinued", BooleanType()), StructField("created_date", DateType())
    ]),
    "orders": StructType([
        StructField("order_id", StringType(), False), StructField("customer_id", StringType(), False),
        StructField("order_timestamp", TimestampType()), StructField("order_status", StringType()),
        StructField("sales_channel", StringType()), StructField("payment_method", StringType()),
        StructField("shipping_city", StringType()), StructField("shipping_country_code", StringType()),
        StructField("shipping_cost_eur", DecimalType(10, 2)), StructField("discount_code", StringType())
    ]),
    "order_items": StructType([
        StructField("order_item_id", StringType(), False), StructField("order_id", StringType(), False),
        StructField("product_id", StringType(), False), StructField("quantity", IntegerType()),
        StructField("unit_price_eur", DecimalType(10, 2)), StructField("discount_pct", DecimalType(5, 4)),
        StructField("line_total_eur", DecimalType(12, 2))
    ])
}

tables = {}
for name, schema in schemas.items():
    tables[name] = (
        spark.read.option("header", True).option("encoding", "UTF-8")
        .schema(schema).csv(f"{base_path}/{name}.csv")
    )
    tables[name].createOrReplaceTempView(name)
    print(name, tables[name].count())

# COMMAND ----------
display(spark.sql("""
SELECT date_trunc('month', o.order_timestamp) AS month,
       p.category,
       ROUND(SUM(oi.line_total_eur), 2) AS revenue_eur,
       SUM(oi.quantity) AS units
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN products p ON oi.product_id = p.product_id
WHERE o.order_status NOT IN ('cancelled', 'returned')
GROUP BY 1, 2
ORDER BY 1, 2
"""))

# COMMAND ----------
# Optional: als verwaltete Delta-Tabellen speichern.
# for name, df in tables.items():
#     df.write.mode("overwrite").format("delta").saveAsTable(f"main.default.{name}")
