"""The SQL console must only ever run a single read statement."""
import unittest
from db_manager import ApiError
from sql_console import check_sql

PG, MY = "postgresql", "mysql"


class AllowedStatements(unittest.TestCase):
    def assertAllowed(self, db, sql, expected=None):
        out = check_sql(sql, db)
        if expected is not None:
            self.assertEqual(out, expected)

    def test_trailing_semicolons_and_comments_are_removed(self):
        self.assertAllowed(PG, "SELECT 1;", "SELECT 1")
        self.assertAllowed(PG, "  select * from t where a = 'x;y' ;; ", "  select * from t where a = 'x;y'")
        self.assertAllowed(PG, "SELECT 1; -- trailing comment", "SELECT 1")
        self.assertAllowed(MY, "SELECT `a;b` FROM t # ;", "SELECT `a;b` FROM t")

    def test_read_statements(self):
        for sql in ["-- comment\nSELECT 1", "WITH x AS (SELECT 1) SELECT * FROM x",
                    "(SELECT 1) UNION (SELECT 2)", "VALUES (1)", "EXPLAIN SELECT 1", "SHOW search_path"]:
            self.assertAllowed(PG, sql)
        for sql in ["SHOW TABLES", "DESCRIBE t", "DESC t", "EXPLAIN SELECT 1"]:
            self.assertAllowed(MY, sql)

    def test_semicolons_inside_strings_names_and_comments(self):
        self.assertAllowed(PG, "SELECT $$ ; DROP TABLE t $$")
        self.assertAllowed(PG, "SELECT $tag$ it's ; $tag$")
        self.assertAllowed(PG, "/* outer /* nested ; */ still */ SELECT 1")
        self.assertAllowed(PG, 'SELECT "we;ird" FROM t')
        self.assertAllowed(PG, r"SELECT e'it\'s'")
        self.assertAllowed(MY, r"SELECT 'a\'; DROP TABLE t; #'")  # all one string in MySQL


class RejectedStatements(unittest.TestCase):
    def assertRejected(self, db, sql, **kw):
        with self.assertRaises(ApiError):
            check_sql(sql, db, **kw)

    def test_writes_and_session_changes(self):
        for sql in ["DELETE FROM t", "UPDATE t SET a = 1", "INSERT INTO t VALUES (1)", "DROP TABLE t",
                    "SET default_transaction_read_only = off", "COMMIT", "BEGIN", "COPY t TO '/tmp/x'"]:
            self.assertRejected(PG, sql)
        for sql in ["UPDATE t SET a = 1", "SET SESSION TRANSACTION READ WRITE", "LOAD DATA INFILE 'x' INTO TABLE t"]:
            self.assertRejected(MY, sql)

    def test_second_statement(self):
        self.assertRejected(PG, "SELECT 1; DELETE FROM t")
        self.assertRejected(MY, "SELECT 'a'; DROP TABLE t")

    def test_second_statement_hidden_with_quote_tricks(self):
        # E-string: \' is an escaped quote, so the server sees real code after it
        self.assertRejected(PG, r"SELECT E'\''; COMMIT; DELETE FROM t; --'")
        # Plain PostgreSQL string: backslash is literal, so the string ends early
        self.assertRejected(PG, r"SELECT 'a\'; DELETE FROM t; --'")
        # MySQL with NO_BACKSLASH_ESCAPES ends the string at \'
        self.assertRejected(MY, r"SELECT 'a\'; DROP TABLE t; #'", mysql_backslash=False)

    def test_file_writes_and_executable_comments(self):
        self.assertRejected(MY, "SELECT * FROM t INTO OUTFILE '/tmp/x'")
        self.assertRejected(MY, "SELECT * FROM t into   dumpfile 'x'")
        self.assertRejected(MY, "SELECT 1 /*! ; DROP TABLE t */")

    def test_unterminated_and_empty(self):
        self.assertRejected(PG, "SELECT 1 /* unterminated")
        self.assertRejected(PG, "SELECT 'unterminated")
        self.assertRejected(PG, "SELECT $x$ unterminated")
        self.assertRejected(PG, "  ;  -- nothing")


if __name__ == "__main__":
    unittest.main()
