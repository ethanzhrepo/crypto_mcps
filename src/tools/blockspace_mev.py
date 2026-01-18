"""
blockspace_mev tool implementation.
"""
import time
from datetime import datetime
from typing import Optional

import structlog

from src.core.models import BlockspaceMevInput, BlockspaceMevOutput, SourceMeta
from src.data_sources.flashbots import FlashbotsMevClient
from src.data_sources.etherscan.client import EtherscanClient
from src.utils.config import config

logger = structlog.get_logger()


class BlockspaceMevTool:
    """Blockspace + MEV-Boost tool."""

    def __init__(
        self,
        flashbots_client: Optional[FlashbotsMevClient] = None,
        etherscan_client: Optional[EtherscanClient] = None,
    ):
        self.flashbots = flashbots_client or FlashbotsMevClient()
        self.etherscan = etherscan_client
        logger.info("blockspace_mev_tool_initialized")

    async def execute(self, params) -> BlockspaceMevOutput:
        if isinstance(params, dict):
            params = BlockspaceMevInput(**params)

        start_time = time.time()
        warnings: list[str] = []
        source_metas: list[SourceMeta] = []
        mev_boost: dict = {}
        gas_oracle: Optional[dict] = None

        try:
            builder_blocks, meta = await self.flashbots.get_builder_blocks_received(limit=params.limit)
            source_metas.append(meta)
            proposer_blocks, meta2 = await self.flashbots.get_proposer_payload_delivered(limit=params.limit)
            source_metas.append(meta2)

            def _to_int(value):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return 0

            def _value_wei(row):
                if not isinstance(row, dict):
                    return 0
                return _to_int(row.get("value"))

            def _builder_key(row):
                if not isinstance(row, dict):
                    return "unknown"
                return (
                    row.get("builder_pubkey")
                    or row.get("builder")
                    or row.get("builderPubkey")
                    or "unknown"
                )

            def _relay_key(row):
                if not isinstance(row, dict):
                    return "flashbots"
                return (
                    row.get("relay")
                    or row.get("relay_pubkey")
                    or row.get("relayPubkey")
                    or "flashbots"
                )

            def _timestamp_ms(row):
                if not isinstance(row, dict):
                    return 0
                ts = row.get("timestamp_ms")
                if ts is None:
                    ts = row.get("timestamp")
                if ts is None:
                    ts = row.get("timestampMs")
                if ts is None:
                    return 0
                try:
                    ts_val = float(ts)
                    # Heuristic: seconds vs ms
                    return int(ts_val * 1000) if ts_val < 1e12 else int(ts_val)
                except (TypeError, ValueError):
                    return 0

            def _format_timestamp(ms):
                if not ms:
                    return None
                return datetime.utcfromtimestamp(ms / 1000).isoformat() + "Z"

            builder_rows = builder_blocks if isinstance(builder_blocks, list) else []
            proposer_rows = proposer_blocks if isinstance(proposer_blocks, list) else []

            builder_total_wei = sum(_value_wei(row) for row in builder_rows)
            proposer_total_wei = sum(_value_wei(row) for row in proposer_rows)

            proposer_count = len(proposer_rows)
            total_value_eth = proposer_total_wei / 1e18 if proposer_total_wei else 0.0
            avg_value_eth = (
                total_value_eth / proposer_count if proposer_count else 0.0
            )

            # Top builders by delivered payloads
            builder_stats = {}
            for row in proposer_rows:
                key = _builder_key(row)
                builder_stats.setdefault(key, {"count": 0, "value_wei": 0})
                builder_stats[key]["count"] += 1
                builder_stats[key]["value_wei"] += _value_wei(row)

            top_builders = []
            for key, stats in sorted(
                builder_stats.items(),
                key=lambda item: item[1]["count"],
                reverse=True,
            )[:10]:
                share = (
                    stats["count"] / proposer_count if proposer_count else 0
                )
                top_builders.append(
                    {
                        "builder": key,
                        "blocks": stats["count"],
                        "value_wei": stats["value_wei"],
                        "share": round(share, 6),
                    }
                )

            # Top relays (Flashbots relay by default)
            relay_stats = {}
            for row in proposer_rows:
                key = _relay_key(row)
                relay_stats.setdefault(key, 0)
                relay_stats[key] += 1

            top_relays = []
            for key, count in sorted(
                relay_stats.items(), key=lambda item: item[1], reverse=True
            )[:10]:
                share = count / proposer_count if proposer_count else 0
                top_relays.append(
                    {"relay": key, "blocks": count, "share": round(share, 6)}
                )

            # Recent blocks (latest first)
            recent_blocks = []
            for row in sorted(
                proposer_rows, key=_timestamp_ms, reverse=True
            )[:10]:
                value_wei = _value_wei(row)
                recent_blocks.append(
                    {
                        "block_number": row.get("block_number")
                        or row.get("blockNumber"),
                        "value_wei": value_wei,
                        "value_eth": value_wei / 1e18 if value_wei else 0.0,
                        "builder": _builder_key(row),
                        "relay": _relay_key(row),
                        "timestamp": _format_timestamp(_timestamp_ms(row)),
                    }
                )

            mev_boost = {
                "builder_blocks_received": builder_blocks,
                "proposer_payload_delivered": proposer_blocks,
                "summary": {
                    "builder_blocks_count": len(builder_rows),
                    "proposer_blocks_count": proposer_count,
                    "total_builder_value_wei": builder_total_wei,
                    "total_proposer_value_wei": proposer_total_wei,
                    "total_proposer_value_eth": total_value_eth,
                    "avg_proposer_value_eth": avg_value_eth,
                },
                "top_builders": top_builders,
                "top_relays": top_relays,
                "recent_blocks": recent_blocks,
            }
        except Exception as exc:
            logger.warning("flashbots_fetch_failed", error=str(exc))
            warnings.append(f"Flashbots MEV-Boost fetch failed: {exc}")

        eth_price_usd: Optional[float] = None
        if params.chain.lower() != "ethereum":
            warnings.append("Gas oracle currently supports ethereum only.")
        else:
            etherscan = self.etherscan or EtherscanClient(
                chain="ethereum",
                api_key=config.get_api_key("etherscan"),
            )
            try:
                gas_oracle = await etherscan.get_gas_oracle()
            except Exception as exc:
                logger.warning("etherscan_gas_oracle_failed", error=str(exc))
                warnings.append(f"Etherscan gas oracle fetch failed: {exc}")

            try:
                price_data = await etherscan.get_eth_price()
                if isinstance(price_data, dict) and price_data.get("status") == "1":
                    result = price_data.get("result", {})
                    eth_price_usd = float(result.get("ethusd", 0) or 0)
            except Exception as exc:
                logger.warning("etherscan_eth_price_failed", error=str(exc))
                warnings.append(f"Etherscan ETH price fetch failed: {exc}")

        if mev_boost and eth_price_usd:
            summary = mev_boost.get("summary") or {}
            total_eth = summary.get("total_proposer_value_eth") or 0.0
            avg_eth = summary.get("avg_proposer_value_eth") or 0.0
            summary["total_proposer_value_usd"] = total_eth * eth_price_usd
            summary["avg_proposer_value_usd"] = avg_eth * eth_price_usd
            mev_boost["summary"] = summary

            for row in mev_boost.get("recent_blocks", []) or []:
                value_eth = row.get("value_eth") or 0.0
                row["value_usd"] = value_eth * eth_price_usd

        elapsed = time.time() - start_time
        logger.info(
            "blockspace_mev_execute_complete",
            chain=params.chain,
            elapsed_ms=round(elapsed * 1000, 2),
        )

        return BlockspaceMevOutput(
            chain=params.chain,
            mev_boost=mev_boost,
            gas_oracle=gas_oracle,
            source_meta=source_metas,
            warnings=warnings,
            as_of_utc=datetime.utcnow(),
        )
