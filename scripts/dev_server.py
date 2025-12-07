#!/usr/bin/env python3
"""
开发服务器启动脚本

使用方式:
    python scripts/dev_server.py
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.server.app import main

if __name__ == "__main__":
    print("=" * 60)
    print("Hubrium MCP Server - Development Mode")
    print("=" * 60)
    print()
    print("Starting server...")
    print()

    try:
        main()
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)
