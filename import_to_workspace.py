"""Import the project CSV data into the configured Databricks workspace via CLI."""
import csv
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parent
CLI = ROOT / '.codex_tmp/databricks_cli/databricks.exe'
DATA = ROOT / 'outputs/databricks_ecommerce_sample'
WAREHOUSE = 'eec1a0f03fb37a5f'
TARGET = 'default_data.default'
TYPES = {
    'customers': ['STRING'] * 8 + ['DATE', 'STRING', 'STRING', 'BOOLEAN'],
    'products': ['STRING'] * 5 + ['DECIMAL(10,2)', 'DECIMAL(10,2)', 'INT', 'BOOLEAN', 'DATE'],
    'orders': ['STRING', 'STRING', 'TIMESTAMP'] + ['STRING'] * 5 + ['DECIMAL(10,2)', 'STRING'],
    'order_items': ['STRING'] * 3 + ['INT', 'DECIMAL(10,2)', 'DECIMAL(5,4)', 'DECIMAL(12,2)'],
}
COUNTS = dict(customers=100, products=50, orders=300, order_items=904)

def api(method, endpoint, payload=None):
    args = [str(CLI), 'api', method, endpoint, '--profile', 'DATA_PROJECT', '--output', 'json']
    if payload is not None:
        request = ROOT / '.codex_tmp/sql_request.json'
        request.write_text(json.dumps(payload), encoding='utf-8')
        args += ['--json', '@' + str(request)]
    result = subprocess.run(args, check=True, capture_output=True, text=True, encoding='utf-8')
    return json.loads(result.stdout)

def sql(statement):
    result = api('post', '/api/2.0/sql/statements', {
        'warehouse_id': WAREHOUSE, 'statement': statement, 'wait_timeout': '10s',
        'on_wait_timeout': 'CONTINUE',
    })
    deadline = time.monotonic() + 600
    while result['status']['state'] in ('PENDING', 'RUNNING'):
        if time.monotonic() > deadline:
            raise TimeoutError(f"Statement still running: {result['statement_id']}")
        time.sleep(2)
        result = api('get', '/api/2.0/sql/statements/' + result['statement_id'])
    if result['status']['state'] != 'SUCCEEDED':
        raise RuntimeError(json.dumps(result['status']))
    return result.get('result', {}).get('data_array', [])

def literal(value):
    return 'NULL' if value == '' else "'" + value.replace("'", "''") + "'"

def main():
    existing = sql('SHOW TABLES IN default_data.default')
    collisions = [row[1] for row in existing if row[1] in TYPES]
    if collisions:
        raise RuntimeError(f'Tables already exist, no changes made: {collisions}')
    statements = {}
    for name, types in TYPES.items():
        with (DATA / f'{name}.csv').open(encoding='utf-8', newline='') as handle:
            reader = csv.reader(handle)
            headers = next(reader)
            rows = list(reader)
        assert len(rows) == COUNTS[name]
        assert len(headers) == len(types)
        values = ',\n'.join('(' + ','.join(map(literal, row)) + ')' for row in rows)
        projection = ', '.join(f'CAST(`{col}` AS {dtype}) AS `{col}`' for col, dtype in zip(headers, types))
        aliases = ','.join(f'`{col}`' for col in headers)
        statements[name] = f'CREATE TABLE {TARGET}.{name} USING DELTA AS SELECT {projection} FROM VALUES {values} AS source({aliases})'
    for name, statement in statements.items():
        sql(statement)
        count = int(sql(f'SELECT COUNT(*) FROM {TARGET}.{name}')[0][0])
        assert count == COUNTS[name], (name, count)
        print(f'Created and verified: {TARGET}.{name} ({count} rows)', flush=True)
    for name, key in [('customers', 'customer_id'), ('products', 'product_id'), ('orders', 'order_id'), ('order_items', 'order_item_id')]:
        assert int(sql(f'SELECT COUNT(*) - COUNT(DISTINCT {key}) FROM {TARGET}.{name}')[0][0]) == 0
    for child, parent, key in [('orders', 'customers', 'customer_id'), ('order_items', 'orders', 'order_id'), ('order_items', 'products', 'product_id')]:
        assert int(sql(f'SELECT COUNT(*) FROM {TARGET}.{child} c LEFT ANTI JOIN {TARGET}.{parent} p ON c.{key} = p.{key}')[0][0]) == 0
    assert int(sql(f'SELECT COUNT(*) FROM {TARGET}.order_items WHERE line_total_eur IS NULL OR line_total_eur != ROUND(quantity * unit_price_eur * (1-discount_pct), 2)')[0][0]) == 0
    print('Primary keys, foreign keys and monetary calculations verified.', flush=True)

if __name__ == '__main__':
    main()
