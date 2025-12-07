"""
指标收集模块

提供Prometheus风格的metrics收集：
- 请求计数器
- 响应时间直方图
- 活跃请求gauge
- 错误计数器
"""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Counter:
    """计数器指标"""

    name: str
    help_text: str
    value: int = 0
    labels: Dict[str, str] = field(default_factory=dict)

    def inc(self, amount: int = 1):
        """增加计数"""
        self.value += amount

    def get(self) -> int:
        """获取当前值"""
        return self.value


@dataclass
class Gauge:
    """仪表盘指标（可增可减）"""

    name: str
    help_text: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float):
        """设置值"""
        self.value = value

    def inc(self, amount: float = 1.0):
        """增加"""
        self.value += amount

    def dec(self, amount: float = 1.0):
        """减少"""
        self.value -= amount

    def get(self) -> float:
        """获取当前值"""
        return self.value


@dataclass
class Histogram:
    """直方图指标"""

    name: str
    help_text: str
    buckets: List[float]
    labels: Dict[str, str] = field(default_factory=dict)
    observations: List[float] = field(default_factory=list)
    sum: float = 0.0
    count: int = 0

    def observe(self, value: float):
        """记录观测值"""
        self.observations.append(value)
        self.sum += value
        self.count += 1

    def get_buckets(self) -> Dict[float, int]:
        """获取桶计数"""
        bucket_counts = {b: 0 for b in self.buckets}
        bucket_counts[float("inf")] = 0

        for obs in self.observations:
            for bucket in sorted(self.buckets):
                if obs <= bucket:
                    bucket_counts[bucket] += 1
            bucket_counts[float("inf")] += 1

        return bucket_counts

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.observations:
            return {
                "count": 0,
                "sum": 0.0,
                "avg": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
            }

        sorted_obs = sorted(self.observations)
        count = len(sorted_obs)

        return {
            "count": count,
            "sum": self.sum,
            "avg": self.sum / count if count > 0 else 0,
            "min": sorted_obs[0],
            "max": sorted_obs[-1],
            "p50": sorted_obs[int(count * 0.5)],
            "p95": sorted_obs[int(count * 0.95)] if count > 20 else sorted_obs[-1],
            "p99": sorted_obs[int(count * 0.99)] if count > 100 else sorted_obs[-1],
        }


class MetricsCollector:
    """
    Metrics收集器

    收集和暴露Prometheus风格的metrics
    """

    def __init__(self):
        """初始化metrics收集器"""
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._lock = Lock()

        # 初始化内置指标
        self._init_default_metrics()

        logger.info("metrics_collector_initialized")

    def _init_default_metrics(self):
        """初始化默认指标"""
        # 请求计数器（按工具和状态）
        self.register_counter(
            "mcp_tool_requests_total",
            "Total number of MCP tool requests",
        )

        # 请求成功计数器
        self.register_counter(
            "mcp_tool_requests_success_total",
            "Total number of successful MCP tool requests",
        )

        # 请求失败计数器
        self.register_counter(
            "mcp_tool_requests_failed_total",
            "Total number of failed MCP tool requests",
        )

        # 活跃请求数
        self.register_gauge(
            "mcp_active_requests",
            "Number of active MCP tool requests",
        )

        # 请求耗时直方图（毫秒）
        self.register_histogram(
            "mcp_request_duration_ms",
            "MCP tool request duration in milliseconds",
            buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000, 10000],
        )

        # 数据源请求计数器
        self.register_counter(
            "data_source_requests_total",
            "Total number of data source requests",
        )

        # 数据源错误计数器
        self.register_counter(
            "data_source_errors_total",
            "Total number of data source errors",
        )

        # 数据源响应时间
        self.register_histogram(
            "data_source_response_time_ms",
            "Data source response time in milliseconds",
            buckets=[50, 100, 250, 500, 1000, 2500, 5000],
        )

        # 断路器状态
        self.register_gauge(
            "circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=half_open, 2=open)",
        )

        # 速率限制器耗尽次数
        self.register_counter(
            "rate_limiter_exhausted_total",
            "Total number of rate limit exhaustions",
        )

    def register_counter(self, name: str, help_text: str) -> Counter:
        """注册计数器"""
        with self._lock:
            if name not in self._counters:
                self._counters[name] = Counter(name=name, help_text=help_text)
            return self._counters[name]

    def register_gauge(self, name: str, help_text: str) -> Gauge:
        """注册仪表盘"""
        with self._lock:
            if name not in self._gauges:
                self._gauges[name] = Gauge(name=name, help_text=help_text)
            return self._gauges[name]

    def register_histogram(
        self,
        name: str,
        help_text: str,
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        """注册直方图"""
        if buckets is None:
            buckets = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]

        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = Histogram(
                    name=name,
                    help_text=help_text,
                    buckets=buckets,
                )
            return self._histograms[name]

    def inc_counter(self, name: str, amount: int = 1, labels: Optional[Dict] = None):
        """增加计数器"""
        counter = self._counters.get(name)
        if counter:
            counter.inc(amount)
            if labels:
                counter.labels.update(labels)

    def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None):
        """设置仪表盘值"""
        gauge = self._gauges.get(name)
        if gauge:
            gauge.set(value)
            if labels:
                gauge.labels.update(labels)

    def observe_histogram(
        self, name: str, value: float, labels: Optional[Dict] = None
    ):
        """记录直方图观测值"""
        histogram = self._histograms.get(name)
        if histogram:
            histogram.observe(value)
            if labels:
                histogram.labels.update(labels)

    def record_tool_request(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
    ):
        """
        记录工具请求

        Args:
            tool_name: 工具名称
            duration_ms: 耗时（毫秒）
            success: 是否成功
        """
        self.inc_counter("mcp_tool_requests_total", labels={"tool": tool_name})

        if success:
            self.inc_counter(
                "mcp_tool_requests_success_total", labels={"tool": tool_name}
            )
        else:
            self.inc_counter(
                "mcp_tool_requests_failed_total", labels={"tool": tool_name}
            )

        self.observe_histogram(
            "mcp_request_duration_ms", duration_ms, labels={"tool": tool_name}
        )

    def record_data_source_request(
        self,
        source_name: str,
        duration_ms: float,
        success: bool,
        error_type: Optional[str] = None,
    ):
        """
        记录数据源请求

        Args:
            source_name: 数据源名称
            duration_ms: 耗时（毫秒）
            success: 是否成功
            error_type: 错误类型（如果失败）
        """
        self.inc_counter(
            "data_source_requests_total", labels={"source": source_name}
        )

        if not success:
            self.inc_counter(
                "data_source_errors_total",
                labels={"source": source_name, "error_type": error_type or "unknown"},
            )

        self.observe_histogram(
            "data_source_response_time_ms",
            duration_ms,
            labels={"source": source_name},
        )

    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        with self._lock:
            metrics = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "counters": {},
                "gauges": {},
                "histograms": {},
            }

            # 收集计数器
            for name, counter in self._counters.items():
                metrics["counters"][name] = {
                    "value": counter.get(),
                    "labels": counter.labels,
                    "help": counter.help_text,
                }

            # 收集仪表盘
            for name, gauge in self._gauges.items():
                metrics["gauges"][name] = {
                    "value": gauge.get(),
                    "labels": gauge.labels,
                    "help": gauge.help_text,
                }

            # 收集直方图
            for name, histogram in self._histograms.items():
                metrics["histograms"][name] = {
                    "stats": histogram.get_stats(),
                    "buckets": histogram.get_buckets(),
                    "labels": histogram.labels,
                    "help": histogram.help_text,
                }

            return metrics

    def export_prometheus(self) -> str:
        """
        导出Prometheus格式的metrics

        Returns:
            Prometheus文本格式
        """
        lines = []

        with self._lock:
            # 导出计数器
            for counter in self._counters.values():
                lines.append(f"# HELP {counter.name} {counter.help_text}")
                lines.append(f"# TYPE {counter.name} counter")
                label_str = self._format_labels(counter.labels)
                lines.append(f"{counter.name}{label_str} {counter.value}")

            # 导出仪表盘
            for gauge in self._gauges.values():
                lines.append(f"# HELP {gauge.name} {gauge.help_text}")
                lines.append(f"# TYPE {gauge.name} gauge")
                label_str = self._format_labels(gauge.labels)
                lines.append(f"{gauge.name}{label_str} {gauge.value}")

            # 导出直方图
            for histogram in self._histograms.values():
                lines.append(f"# HELP {histogram.name} {histogram.help_text}")
                lines.append(f"# TYPE {histogram.name} histogram")
                label_str = self._format_labels(histogram.labels)

                # 桶计数
                buckets = histogram.get_buckets()
                for bucket, count in sorted(buckets.items()):
                    bucket_label = (
                        label_str.rstrip("}") + f',le="{bucket}"}}'
                        if label_str
                        else f'{{le="{bucket}"}}'
                    )
                    lines.append(f"{histogram.name}_bucket{bucket_label} {count}")

                # 总计和数量
                lines.append(f"{histogram.name}_sum{label_str} {histogram.sum}")
                lines.append(f"{histogram.name}_count{label_str} {histogram.count}")

        return "\n".join(lines) + "\n"

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """格式化标签为Prometheus格式"""
        if not labels:
            return ""

        label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ",".join(label_pairs) + "}"

    def reset(self):
        """重置所有指标（主要用于测试）"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._init_default_metrics()


# 全局metrics收集器实例
global_metrics_collector = MetricsCollector()
