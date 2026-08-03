"""app/core/metrics.py — High-performance, lightweight Metrics Collector abstraction for Prometheus exposition."""

from __future__ import annotations

import threading
from collections import defaultdict


class MetricsCollector:
    """Thread-safe metrics registry supporting Counters, Gauges, and Histograms with Prometheus format generation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def inc_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        key = self._format_key(name, labels)
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        key = self._format_key(name, labels)
        with self._lock:
            self._gauges[key] = value

    def inc_gauge(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment a gauge metric."""
        key = self._format_key(name, labels)
        with self._lock:
            self._gauges[key] += value

    def dec_gauge(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Decrement a gauge metric."""
        key = self._format_key(name, labels)
        with self._lock:
            self._gauges[key] -= value

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record an observation in a histogram metric."""
        key = self._format_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)

    def _format_key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def export_prometheus(self) -> str:
        """Export all registered metrics into Prometheus exposition text format."""
        lines: list[str] = []

        with self._lock:
            # Export Counters
            for key, val in sorted(self._counters.items()):
                metric_name = key.split("{")[0]
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{key} {val}")

            # Export Gauges
            for key, val in sorted(self._gauges.items()):
                metric_name = key.split("{")[0]
                lines.append(f"# TYPE {metric_name} gauge")
                lines.append(f"{key} {val}")

            # Export Histograms
            for key, observations in sorted(self._histograms.items()):
                metric_name = key.split("{")[0]
                lines.append(f"# TYPE {metric_name} summary")
                count = len(observations)
                total_sum = sum(observations)
                lines.append(f"{key}_count {count}")
                lines.append(f"{key}_sum {round(total_sum, 4)}")

        return "\n".join(lines) + "\n" if lines else ""


# Global singleton instance
METRICS = MetricsCollector()
