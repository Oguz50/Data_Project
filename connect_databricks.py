"""Query Databricks from the local virtual environment using OAuth profile DATA_PROJECT."""
import os
from pathlib import Path
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

HOST = 'https://dbc-2d7162b3-2573.cloud.databricks.com'
WAREHOUSE_ID = 'eec1a0f03fb37a5f'
PROFILE = 'DATA_PROJECT'


def connect():
    """Reuse the CLI login without putting access tokens in source files."""
    cli_dir = Path(__file__).resolve().parent / '.codex_tmp' / 'databricks_cli'
    if (cli_dir / 'databricks.exe').is_file():
        os.environ['PATH'] = str(cli_dir) + os.pathsep + os.environ.get('PATH', '')
    return WorkspaceClient(host=HOST, profile=PROFILE)


def query(statement, *, client=None, timeout=300):
    """Execute SQL and return all inline result chunks as a list of dictionaries.

    Values are returned in the SQL API's string representation (or None).
    Intended for small interactive query results, not bulk exports.
    """
    client = client or connect()
    response = client.statement_execution.execute_statement(
        statement=statement, warehouse_id=WAREHOUSE_ID,
        catalog='default_data', schema='default', wait_timeout='10s',
    )
    deadline = time.monotonic() + timeout
    while response.status and response.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.monotonic() >= deadline:
            client.statement_execution.cancel_execution(response.statement_id)
            raise TimeoutError(f'SQL query exceeded {timeout}s; cancellation requested.')
        time.sleep(2)
        response = client.statement_execution.get_statement(response.statement_id)
    if not response.status or response.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f'SQL query failed: {response.status}')
    if response.manifest and response.manifest.truncated:
        raise RuntimeError('SQL result was truncated. Use LIMIT or a bulk export.')
    if not response.result or not response.manifest or not response.manifest.schema:
        return []
    columns = [column.name for column in response.manifest.schema.columns]
    chunk = response.result
    rows = []
    while True:
        rows.extend(dict(zip(columns, row)) for row in (chunk.data_array or []))
        if chunk.next_chunk_index is None:
            return rows
        chunk = client.statement_execution.get_statement_result_chunk_n(
            response.statement_id, chunk.next_chunk_index,
        )


def main():
    client = connect()
    client.current_user.me()
    print(f'Connected to {HOST} using {PROFILE}', flush=True)
    rows = query("""
        SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM customers
        UNION ALL SELECT 'products', COUNT(*) FROM products
        UNION ALL SELECT 'orders', COUNT(*) FROM orders
        UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
    """, client=client)
    for row in rows:
        print(f"{row['table_name']}: {row['row_count']} rows", flush=True)


if __name__ == '__main__':
    main()
