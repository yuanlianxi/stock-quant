"""
locust 性能测试（Phase 6.2）

用法：
    # 启动 uvicorn
    nohup python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level warning &

    # 跑 locust
    locust -f tests/locustfile.py --host http://localhost:8000
    # 或 headless
    python3 -m locust -f tests/locustfile.py --headless --host http://localhost:8000 \
             -u 10 -r 2 -t 5s --csv=/tmp/locust-p6.2 --html=/tmp/locust-p6.2.html

设计：
- 3 类查询按权重分布（策略 3 / 账户 2 / session 1 / list 1 / 合约 1 / 日线 1）
- 故意混入不存在的 session_id（测 404 性能）
- 不写操作（避免污染 prod DB）
"""
import random

from locust import HttpUser, between, task


SYMBOLS = ["AG", "AU", "RB", "TA", "CU"]
ACCOUNTS = ["sim_default", "sim_user1", "sim_user2"]
STRATEGY_IDS = ["turtle_v1"]


class StockQuantUser(HttpUser):
    """模拟 1 个用户的查询行为"""

    wait_time = between(0.1, 0.5)

    @task(3)
    def view_strategies(self):
        """3 倍权重：查策略列表"""
        self.client.get("/strategies", name="/strategies")

    @task(2)
    def view_account_overview(self):
        """2 倍权重：查账户总览"""
        account = random.choice(ACCOUNTS)
        self.client.get(
            f"/account/overview?account_id={account}",
            name="/account/overview",
        )

    @task(1)
    def view_session_lines(self):
        """1 倍权重：查 session 价格线（不存在的也行——测 404 性能）"""
        self.client.get(
            "/session/non_exist_session/lines",
            name="/session/[id]/lines",
        )

    @task(1)
    def view_open_sessions(self):
        """1 倍权重：查 open sessions 列表"""
        self.client.get(
            "/sessions?status=open",
            name="/sessions?status=open",
        )

    @task(1)
    def view_contracts(self):
        """1 倍权重：查合约列表"""
        symbol = random.choice(SYMBOLS)
        self.client.get(
            f"/contracts/{symbol}",
            name="/contracts/[symbol]",
        )

    @task(1)
    def view_daily(self):
        """1 倍权重：查日线"""
        symbol = random.choice(SYMBOLS)
        self.client.get(
            f"/daily/{symbol}?days=30",
            name="/daily/[symbol]?days=30",
        )
