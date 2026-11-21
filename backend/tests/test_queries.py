"""SQL building: search, filters, sorting, and value conversion."""
import datetime
import decimal
import unittest
import db_manager as dm
from routes.table_routes import js_safe, csv_value

PG = {"db_type": "postgresql", "schema": "public"}
MY = {"db_type": "mysql", "schema": "shop"}
COLS = [{"name": "id", "type": "integer"}, {"name": "name", "type": "text"},
        {"name": "meta", "type": "json"}]


class FakeCursor:
    """Returns queued results from fetchall(), in order."""
    def __init__(self, *results):
        self.results = list(results)
        self.queries = []

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchall(self):
        return self.results.pop(0)


class Where(unittest.TestCase):
    def test_nothing(self):
        self.assertEqual(dm.where_clause(PG, COLS), ("", []))

    def test_search_escapes_like_wildcards(self):
        w, p = dm.where_clause(PG, COLS, "50%_off")
        self.assertEqual(w, " WHERE t::text ILIKE %s")
        self.assertEqual(p, ["%50\\%\\_off%"])

    def test_mysql_search_spans_all_columns(self):
        w, _ = dm.where_clause(MY, COLS, "x")
        self.assertEqual(w, " WHERE CONCAT_WS(' ', t.`id`, t.`name`, t.`meta`) LIKE %s")

    def test_filters_contains_and_exact(self):
        w, p = dm.where_clause(PG, COLS, "", {"id": "=5", "name": "bo"})
        self.assertEqual(w, ' WHERE t."id"::text = %s AND t."name"::text ILIKE %s')
        self.assertEqual(p, ["5", "%bo%"])

    def test_unknown_filter_column_is_rejected(self):
        with self.assertRaises(dm.ApiError):
            dm.where_clause(PG, COLS, "", {'id" = 1 OR "1': "x"})

    def test_quoted_names_cannot_break_out(self):
        self.assertEqual(dm.quote(PG, 'a"b'), '"a""b"')
        self.assertEqual(dm.quote(MY, "a`b"), "`a``b`")

    def test_parse_filters(self):
        self.assertEqual(dm.parse_filters(""), {})
        self.assertEqual(dm.parse_filters('{"a": 1, "b": "", "c": null}'), {"a": "1"})
        for bad in ["[1]", "not json"]:
            with self.assertRaises(dm.ApiError):
                dm.parse_filters(bad)


class Order(unittest.TestCase):
    table = {"name": "t", "kind": "table"}
    view = {"name": "v", "kind": "view"}

    def test_primary_key(self):
        cur = FakeCursor([("id",)])
        self.assertEqual(dm.order_clause(cur, PG, self.table, COLS), ' ORDER BY t."id"')

    def test_pg_table_without_key_uses_ctid(self):
        self.assertEqual(dm.order_clause(FakeCursor([]), PG, self.table, COLS), " ORDER BY t.ctid")

    def test_pg_view_skips_unsortable_types(self):
        self.assertEqual(dm.order_clause(FakeCursor([]), PG, self.view, COLS), ' ORDER BY t."id", t."name"')

    def test_mysql_without_key_uses_all_columns(self):
        self.assertEqual(dm.order_clause(FakeCursor([]), MY, self.table, COLS),
                         " ORDER BY t.`id`, t.`name`, t.`meta`")

    def test_user_sort_comes_first_then_key(self):
        cur = FakeCursor([("id",)])
        self.assertEqual(dm.order_clause(cur, PG, self.table, COLS, "name", "desc"),
                         ' ORDER BY t."name" DESC, t."id"')
        cur = FakeCursor([("id",)])
        self.assertEqual(dm.order_clause(cur, PG, self.table, COLS, "id", "desc"), ' ORDER BY t."id" DESC')

    def test_unknown_sort_column_is_rejected(self):
        with self.assertRaises(dm.ApiError):
            dm.order_clause(FakeCursor([("id",)]), PG, self.table, COLS, "nope")


class Values(unittest.TestCase):
    def test_js_safe(self):
        self.assertEqual(js_safe(2**60), str(2**60))
        self.assertEqual(js_safe(-(2**60)), str(-(2**60)))
        self.assertEqual(js_safe(2**53 - 1), 2**53 - 1)
        self.assertIs(js_safe(True), True)
        self.assertEqual(js_safe(1.5), 1.5)

    def test_csv_value(self):
        self.assertEqual(csv_value(None), "")
        self.assertEqual(csv_value(b"\x01\xff"), "\\x01ff")
        self.assertEqual(csv_value({"a": "é"}), '{"a": "é"}')
        self.assertEqual(csv_value(decimal.Decimal("1.10")), "1.10")
        self.assertEqual(csv_value(datetime.date(2026, 1, 2)), "2026-01-02")


if __name__ == "__main__":
    unittest.main()
