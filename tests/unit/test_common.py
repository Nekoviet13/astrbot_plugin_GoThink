"""Tests for common infrastructure helpers."""

import unittest

from core.common import BaseRegistry, SystemClock, UUIDGenerator


class CommonInfrastructureTest(unittest.TestCase):
    """Test reusable infrastructure helpers."""

    def test_registry_registers_items_without_singleton_state(self) -> None:
        """Separate registries should not share entries."""
        first: BaseRegistry[str] = BaseRegistry()
        second: BaseRegistry[str] = BaseRegistry()

        first.register("alpha", "value")

        self.assertEqual(first.require("alpha"), "value")
        self.assertIsNone(second.get("alpha"))

    def test_uuid_generator_uses_external_prefix(self) -> None:
        """Generated IDs should accept a caller-provided prefix."""
        generated = UUIDGenerator().new_id("t_")

        self.assertTrue(generated.startswith("t_"))
        self.assertGreater(len(generated), 2)

    def test_system_clock_returns_iso_string(self) -> None:
        """System clock should expose ISO formatted time."""
        value = SystemClock().now_iso()

        self.assertIn("T", value)


if __name__ == "__main__":
    unittest.main()
