import unittest
from dataclasses import FrozenInstanceError

from src.v2.schemas.inbound import InboundEvent


class SchemaTests(unittest.TestCase):
    def test_inbound_event_is_frozen(self):
        event = InboundEvent(role="demo", task="hello", task_id="t1", created_at="now")
        with self.assertRaises(FrozenInstanceError):
            event.role = "changed"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
