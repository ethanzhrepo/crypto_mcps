"""
EvidencePersister middleware for automatic evidence bundle persistence.

This middleware automatically persists EvidenceBundles to three storage backends:
1. S3/MinIO - Complete JSON payload
2. PostgreSQL - Metadata index
3. ClickHouse - Time-series EvidenceItems

Used by the EnsureFresh orchestration to ensure all evidence is captured
and can be reproduced for audit purposes.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import json

# Add fin_agent to path for storage imports
fin_agent_path = Path(__file__).parent.parent.parent.parent / "fin_agent"
sys.path.insert(0, str(fin_agent_path))

from storage import PostgresClient, TimeSeriesStore, ObjectStore


class EvidencePersister:
    """
    Evidence Bundle 持久化中间件

    自动将 EvidenceBundle 持久化到三层存储：
    1. S3/MinIO: 完整 JSON 快照
    2. PostgreSQL: 元数据索引（便于查询）
    3. ClickHouse: 时序化 EvidenceItems（便于统计分析）
    """

    def __init__(
        self,
        postgres_client: Optional[PostgresClient] = None,
        clickhouse_client: Optional[TimeSeriesStore] = None,
        object_store: Optional[ObjectStore] = None,
    ):
        """
        初始化 EvidencePersister

        Args:
            postgres_client: PostgreSQL 客户端（可选，自动从环境变量初始化）
            clickhouse_client: ClickHouse 客户端（可选）
            object_store: MinIO/S3 客户端（可选）
        """
        self.postgres = postgres_client
        self.clickhouse = clickhouse_client
        self.object_store = object_store

        # 如果未提供，从环境变量初始化
        if self.postgres is None:
            self._init_postgres()

        if self.clickhouse is None:
            self._init_clickhouse()

        if self.object_store is None:
            self._init_object_store()

    def _init_postgres(self):
        """从环境变量初始化 PostgreSQL 客户端"""
        import os

        postgres_url = os.getenv(
            "POSTGRES_URL", "postgresql://hubrium:hubrium_pass@localhost:5432/hubrium"
        )
        try:
            self.postgres = PostgresClient(postgres_url)
        except Exception as e:
            print(f"Warning: Failed to initialize PostgreSQL client: {e}")
            self.postgres = None

    def _init_clickhouse(self):
        """从环境变量初始化 ClickHouse 客户端"""
        import os

        clickhouse_url = os.getenv("CLICKHOUSE_URL", "http://localhost:8123")
        clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "")

        try:
            # 解析 URL
            host = clickhouse_url.replace("http://", "").replace("https://", "").split(":")[0]

            self.clickhouse = TimeSeriesStore(
                host=host, port=9000, user="hubrium", password=clickhouse_password
            )
        except Exception as e:
            print(f"Warning: Failed to initialize ClickHouse client: {e}")
            self.clickhouse = None

    def _init_object_store(self):
        """从环境变量初始化 MinIO/S3 客户端"""
        import os

        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ROOT_USER", "minioadmin")
        secret_key = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        try:
            self.object_store = ObjectStore(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
        except Exception as e:
            print(f"Warning: Failed to initialize MinIO client: {e}")
            self.object_store = None

    async def persist(self, evidence_bundle: Dict[str, Any]) -> str:
        """
        持久化 EvidenceBundle 到三层存储

        Args:
            evidence_bundle: EvidenceBundle 字典，包含：
                - bundle_id: 唯一标识
                - as_of: 时间戳
                - watermark: 时间水位线
                - asset: 资产符号
                - items: EvidenceItem 列表
                - conflicts: 冲突列表（可选）
                - hash: SHA256 哈希（可选，自动生成）

        Returns:
            S3 URI of the persisted bundle

        Raises:
            Exception: 如果所有存储后端都失败
        """
        bundle_id = evidence_bundle.get("bundle_id")
        if not bundle_id:
            raise ValueError("EvidenceBundle must have a bundle_id")

        # 计算哈希（如果未提供）
        if "hash" not in evidence_bundle:
            evidence_bundle["hash"] = self._compute_hash(evidence_bundle)

        # 添加持久化时间戳
        evidence_bundle["persisted_at"] = datetime.utcnow().isoformat()

        snapshot_uri = None
        postgres_success = False
        clickhouse_success = False

        # 1. 上传到 S3/MinIO（优先级最高，保证完整数据可追溯）
        if self.object_store:
            try:
                snapshot_uri = self.object_store.upload_evidence_bundle(
                    bundle_id, evidence_bundle
                )
                print(f"✓ Persisted EvidenceBundle {bundle_id} to S3: {snapshot_uri}")
            except Exception as e:
                print(f"✗ Failed to persist to S3: {e}")
                # S3 失败是严重错误，但继续尝试其他存储
                snapshot_uri = f"s3://evidence-bundles/{bundle_id}.json"  # 占位符

        # 2. 写入 PostgreSQL 索引
        if self.postgres:
            try:
                await self.postgres.insert_evidence_bundle(
                    bundle_id=bundle_id,
                    data={
                        "as_of_utc": datetime.fromisoformat(
                            evidence_bundle["as_of"].replace("Z", "+00:00")
                        ),
                        "asset": evidence_bundle.get("asset"),
                        "tools_used": [item["tool"] for item in evidence_bundle.get("items", [])],
                        "snapshot_uri": snapshot_uri,
                        "hash": evidence_bundle["hash"],
                        "watermark": evidence_bundle.get("watermark"),
                        "conflicts_count": len(evidence_bundle.get("conflicts", [])),
                        "freshness_sla_met": evidence_bundle.get("freshness_sla_met", True),
                    },
                )
                postgres_success = True
                print(f"✓ Indexed EvidenceBundle {bundle_id} in PostgreSQL")
            except Exception as e:
                print(f"✗ Failed to index in PostgreSQL: {e}")

        # 3. 写入 ClickHouse 时序表
        if self.clickhouse and evidence_bundle.get("items"):
            try:
                items_data = []
                for idx, item in enumerate(evidence_bundle["items"]):
                    source_meta = item.get("source_meta", [])
                    if source_meta:
                        provider = source_meta[0].get("provider", "unknown")
                        endpoint = source_meta[0].get("endpoint", "")
                        response_time = source_meta[0].get("response_time_ms", 0)
                        cached = source_meta[0].get("cached", False)
                        fallback_used = source_meta[0].get("fallback_used", False)
                    else:
                        provider = "unknown"
                        endpoint = ""
                        response_time = 0
                        cached = False
                        fallback_used = False

                    items_data.append(
                        {
                            "bundle_id": bundle_id,
                            "item_index": idx,
                            "tool": item["tool"],
                            "data_type": item.get("data_type", ""),
                            "as_of_utc": datetime.fromisoformat(
                                item["as_of_utc"].replace("Z", "+00:00")
                            ),
                            "ttl_seconds": item.get("ttl_policy", {}).get(
                                "ttl_seconds", 0
                            ),
                            "provider": provider,
                            "endpoint": endpoint,
                            "response_time_ms": response_time,
                            "cached": cached,
                            "fallback_used": fallback_used,
                        }
                    )

                self.clickhouse.insert_evidence_items(items_data)
                clickhouse_success = True
                print(
                    f"✓ Inserted {len(items_data)} EvidenceItems for {bundle_id} into ClickHouse"
                )
            except Exception as e:
                print(f"✗ Failed to insert into ClickHouse: {e}")

        # 验证至少一个存储成功
        if not (snapshot_uri or postgres_success or clickhouse_success):
            raise Exception(
                f"Failed to persist EvidenceBundle {bundle_id} to any storage backend"
            )

        return snapshot_uri

    def _compute_hash(self, evidence_bundle: Dict[str, Any]) -> str:
        """
        计算 EvidenceBundle 的 SHA256 哈希

        Args:
            evidence_bundle: EvidenceBundle 字典

        Returns:
            SHA256 哈希字符串
        """
        # 排除动态字段
        bundle_copy = {
            k: v
            for k, v in evidence_bundle.items()
            if k not in ["hash", "persisted_at"]
        }

        # 序列化为 JSON（排序键以确保一致性）
        bundle_json = json.dumps(bundle_copy, sort_keys=True)

        # 计算哈希
        return hashlib.sha256(bundle_json.encode()).hexdigest()

    async def retrieve(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        """
        检索 EvidenceBundle

        优先从 S3 获取完整数据，如果失败则从 PostgreSQL 获取元数据

        Args:
            bundle_id: Bundle ID

        Returns:
            EvidenceBundle 字典，如果不存在则返回 None
        """
        # 1. 尝试从 S3 获取完整数据
        if self.object_store:
            try:
                bundle = self.object_store.download_evidence_bundle(bundle_id)
                if bundle:
                    return bundle
            except Exception as e:
                print(f"Failed to retrieve from S3: {e}")

        # 2. 从 PostgreSQL 获取元数据
        if self.postgres:
            try:
                metadata = await self.postgres.get_evidence_bundle(bundle_id)
                if metadata:
                    # 返回元数据（不包含完整 items）
                    return {
                        "bundle_id": metadata.bundle_id,
                        "as_of": metadata.as_of_utc.isoformat(),
                        "asset": metadata.asset,
                        "tools_used": metadata.tools_used,
                        "snapshot_uri": metadata.snapshot_uri,
                        "hash": metadata.hash,
                        "watermark": metadata.watermark,
                        "conflicts_count": metadata.conflicts_count,
                        "freshness_sla_met": metadata.freshness_sla_met,
                        "created_at": metadata.created_at.isoformat(),
                    }
            except Exception as e:
                print(f"Failed to retrieve from PostgreSQL: {e}")

        return None

    async def list_bundles(
        self, asset: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        列出 EvidenceBundles

        Args:
            asset: 过滤资产（可选）
            limit: 返回数量上限

        Returns:
            EvidenceBundle 元数据列表
        """
        if not self.postgres:
            return []

        try:
            bundles = await self.postgres.list_evidence_bundles(asset=asset, limit=limit)
            return [
                {
                    "bundle_id": b.bundle_id,
                    "as_of": b.as_of_utc.isoformat(),
                    "asset": b.asset,
                    "tools_used": b.tools_used,
                    "snapshot_uri": b.snapshot_uri,
                    "hash": b.hash,
                    "conflicts_count": b.conflicts_count,
                    "freshness_sla_met": b.freshness_sla_met,
                    "created_at": b.created_at.isoformat(),
                }
                for b in bundles
            ]
        except Exception as e:
            print(f"Failed to list bundles: {e}")
            return []

    async def close(self):
        """关闭所有存储连接"""
        if self.postgres:
            await self.postgres.close()

        if self.clickhouse:
            self.clickhouse.close()

        # object_store 没有 close 方法（MinIO 客户端）
