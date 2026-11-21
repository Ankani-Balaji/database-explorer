"""Saved connections (expiry) and the database connection pool, without a real database."""
import unittest
from unittest import mock
import db_manager as dm

CFG = {"db_type": "mysql", "host": "h", "port": 3306, "database": "d", "user": "u",
       "password": "p", "schema": "d"}


class FakeConn:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    def ping(self, reconnect=False):
        if self.closed:
            raise RuntimeError("gone")


class Base(unittest.TestCase):
    def setUp(self):
        dm._connections.clear()
        dm._pool.clear()
        self.opened = []

        def fake_open(cfg):
            c = FakeConn()
            self.opened.append(c)
            return c
        patcher = mock.patch.object(dm, "open_conn", side_effect=fake_open)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.clock = [1000.0]
        clock = mock.patch.object(dm.time, "monotonic", side_effect=lambda: self.clock[0])
        clock.start()
        self.addCleanup(clock.stop)


class SavedConnections(Base):
    def test_add_get_remove(self):
        cid = dm.add_connection(dict(CFG))
        self.assertEqual(dm.get_cfg(cid)["host"], "h")
        dm.remove_connection(cid)
        with self.assertRaises(dm.ApiError) as e:
            dm.get_cfg(cid)
        self.assertEqual(e.exception.status, 401)

    def test_idle_connection_expires(self):
        cid = dm.add_connection(dict(CFG))
        self.clock[0] += dm.CONNECTION_IDLE_SECONDS - 1
        dm.get_cfg(cid)  # still alive, and this use resets the idle timer
        self.clock[0] += dm.CONNECTION_IDLE_SECONDS - 1
        dm.get_cfg(cid)
        self.clock[0] += dm.CONNECTION_IDLE_SECONDS + 1
        with self.assertRaises(dm.ApiError):
            dm.get_cfg(cid)


class Pool(Base):
    def test_connection_is_reused(self):
        cid = dm.add_connection(dict(CFG))
        cfg = dm.get_cfg(cid)
        with dm.pooled_conn(cfg) as a:
            pass
        with dm.pooled_conn(cfg) as b:
            pass
        self.assertIs(a, b)
        self.assertEqual(len(self.opened), 1)
        self.assertFalse(a.closed)

    def test_parallel_requests_get_separate_connections(self):
        cfg = dm.get_cfg(dm.add_connection(dict(CFG)))
        with dm.pooled_conn(cfg) as a, dm.pooled_conn(cfg) as b:
            self.assertIsNot(a, b)

    def test_failed_work_closes_the_connection(self):
        cfg = dm.get_cfg(dm.add_connection(dict(CFG)))
        with self.assertRaises(ValueError):
            with dm.pooled_conn(cfg) as a:
                raise ValueError("query failed")
        self.assertTrue(a.closed)
        with dm.pooled_conn(cfg) as b:
            pass
        self.assertIsNot(a, b)

    def test_dead_connection_is_replaced_after_idle(self):
        cfg = dm.get_cfg(dm.add_connection(dict(CFG)))
        with dm.pooled_conn(cfg) as a:
            pass
        a.closed = True  # server dropped it
        self.clock[0] += dm.POOL_CHECK_AFTER + 1
        with dm.pooled_conn(cfg) as b:
            pass
        self.assertIsNot(a, b)

    def test_stale_connection_is_closed(self):
        cfg = dm.get_cfg(dm.add_connection(dict(CFG)))
        with dm.pooled_conn(cfg) as a:
            pass
        self.clock[0] += dm.POOL_IDLE_SECONDS + 1
        with dm.pooled_conn(cfg) as b:
            pass
        self.assertTrue(a.closed)
        self.assertIsNot(a, b)

    def test_disconnect_closes_pooled_connections(self):
        cid = dm.add_connection(dict(CFG))
        with dm.pooled_conn(dm.get_cfg(cid)) as a:
            pass
        dm.remove_connection(cid)
        self.assertTrue(a.closed)
        self.assertEqual(dm._pool, {})

    def test_pool_size_is_capped(self):
        cfg = dm.get_cfg(dm.add_connection(dict(CFG)))
        from contextlib import ExitStack
        with ExitStack() as stack:
            conns = [stack.enter_context(dm.pooled_conn(cfg)) for _ in range(dm.POOL_MAX_IDLE + 2)]
        self.assertEqual(len(dm._pool[dm._key(cfg)]), dm.POOL_MAX_IDLE)
        self.assertEqual(sum(c.closed for c in conns), 2)


if __name__ == "__main__":
    unittest.main()
