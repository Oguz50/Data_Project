"""Manage the project-local Neo4j Community instance without a Windows service."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time

from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / '.local'
NEO4J_HOME = LOCAL / 'neo4j-community-2026.10.1'
JAVA_HOME = LOCAL / 'java' / 'zulu21.54.109-ca-jdk21.0.13.0.3-win_x64'
CREDENTIALS = LOCAL / 'neo4j_credentials.json'


def settings():
    if not CREDENTIALS.exists():
        raise RuntimeError('Run local_neo4j.py start first.')
    return json.loads(CREDENTIALS.read_text(encoding='utf-8'))


def driver():
    config = settings()
    return GraphDatabase.driver(config['uri'], auth=(config['username'], config['password']))


def environment():
    env = os.environ.copy()
    env['JAVA_HOME'] = str(JAVA_HOME)
    env['NEO4J_HOME'] = str(NEO4J_HOME)
    env['PATH'] = str(JAVA_HOME / 'bin') + os.pathsep + env.get('PATH', '')
    return env


def command(admin=False):
    main = 'Neo4jAdminCommand' if admin else 'Neo4jCommand'
    return [str(JAVA_HOME / 'bin/java.exe'), '-cp', str(NEO4J_HOME / 'lib/*'),
            f'-Dbasedir={NEO4J_HOME}', f'org.neo4j.server.startup.{main}']


def port_open(port):
    with socket.socket() as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def start():
    if port_open(7687) or port_open(7474):
        with driver() as connection:
            connection.verify_connectivity()
        print('Neo4j is already running: http://localhost:7474/browser/')
        return
    if not CREDENTIALS.exists():
        config = {'uri': 'bolt://127.0.0.1:7687', 'database': 'neo4j',
                  'username': 'neo4j', 'password': secrets.token_urlsafe(24)}
        # Create exclusively so retries cannot replace existing login information.
        with CREDENTIALS.open('x', encoding='utf-8') as handle:
            json.dump(config, handle, indent=2)
    config = settings()
    if not (NEO4J_HOME / 'data/dbms/auth.ini').exists() and not (NEO4J_HOME / 'data/databases/system').exists():
        result = subprocess.run(command(admin=True) + ['dbms', 'set-initial-password', config['password']],
                                cwd=NEO4J_HOME, env=environment(), capture_output=True, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError('Initial password setup failed: ' + result.stderr)
    log_path = LOCAL / 'neo4j-console.log'
    with log_path.open('ab') as log:
        process = subprocess.Popen(command() + ['console'], cwd=NEO4J_HOME, env=environment(),
                                   stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    print(f'Neo4j starting (launcher PID {process.pid}).', flush=True)
    for _ in range(90):
        if process.poll() is not None:
            raise RuntimeError(f'Neo4j exited; inspect {log_path}')
        if port_open(7687):
            try:
                with driver() as connection:
                    connection.verify_connectivity()
                print('Neo4j ready: http://localhost:7474/browser/', flush=True)
                return
            except Exception:
                pass
        time.sleep(1)
    raise TimeoutError(f'Neo4j is still starting; inspect {log_path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'status', 'console'])
    action = parser.parse_args().action
    if action == 'start':
        start()
    elif action == 'status':
        with driver() as connection:
            connection.verify_connectivity()
            result = connection.execute_query('MATCH (n) RETURN count(n) AS nodes', database_='neo4j')
        print('Connected:', result.records[0]['nodes'], 'nodes')
    else:
        # For manual foreground use, Ctrl+C stops the server normally.
        subprocess.run(command() + ['console'], cwd=NEO4J_HOME, env=environment(), check=True)


if __name__ == '__main__':
    main()
