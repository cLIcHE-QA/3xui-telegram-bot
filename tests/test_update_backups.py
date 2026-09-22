from pathlib import Path
import sqlite3
import tempfile
import unittest

from update_backups import validate_database
from version_service import UpdateError


class BackupValidationTests(unittest.TestCase):
    def test_valid_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.db'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE example(id INTEGER PRIMARY KEY)')
                db.execute('INSERT INTO example VALUES (1)')
            validate_database(path.read_bytes(), 'sample.db')

    def test_html_json_empty_and_corrupt_sqlite_are_rejected(self):
        for body in [b'', b'<html>login</html>', b'{"success":false}', b'SQLite format 3\0' + b'garbage']:
            with self.subTest(body=body), self.assertRaises(UpdateError):
                validate_database(body, 'x-ui.db')

    def test_postgresql_custom_dump_header_sanity(self):
        validate_database(b'PGDMP' + bytes(40), 'node.dump')
        with self.assertRaises(UpdateError):
            validate_database(b'PGDMP', 'node.dump')
        with self.assertRaises(UpdateError):
            validate_database(b'PGDMP' + bytes(40), 'node.db')
