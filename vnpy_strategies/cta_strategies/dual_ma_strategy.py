"""
双均线策略 (Dual Moving Average Strategy)
基于 VN.py CtaTemplate 实现

核心逻辑:
- 快线MA上穿慢线MA → 做多(buy)
- 快线MA下穿慢线MA → 做空/平多(sell)
"""

from vnpy_ctastrategy import CtaTemplate
from vnpy_ctastrategy import ArrayManager, Direction


class DualMAStrategy(CtaTemplate):
    """双均线趋势跟踪策略"""

    # ============ 策略参数 ============
    # 注意: parameters 列表中不能包含非参数属性
    fast_ma: int = 10      # 快速均线周期
    slow_ma: int = 20      # 慢速均线周期
    fixed_size: int = 1    # 每次下单手数

    parameters = [
        "fast_ma",
        "slow_ma",
        "fixed_size"
    ]

    # ============ 策略变量 ============
    # 注意: variables 列表中不能包含参数属性
    pos: int = 0           # 当前持仓量
    fast_ma_value: float = 0.0
    slow_ma_value: float = 0.0

    variables = [
        "pos",
        "fast_ma_value",
        "slow_ma_value"
    ]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        # 数据容器，负责K线合成和指标计算
        self.am = ArrayManager()
        self.bg_count = 0   # BarGenerator 计数（调试用）

    def on_init(self):
        """策略初始化回调"""
        self.write_log("策略初始化...")
        # 加载最近N天K线数据进行预计算
        self.load_bar(10)
        self.write_log("策略初始化完成")

    def on_start(self):
        """策略启动回调"""
        self.write_log("策略启动")

    def on_stop(self):
        """策略停止回调"""
        self.write_log("策略停止")

    def on_bar(self, bar):
        """K线回调（主策略逻辑）"""
        # 更新K线数据到 ArrayManager
        self.am.update_bar(bar)

        # 数据不足预热期，等待
        if not self.am.inited:
            return

        # 计算均线值
        fast_ma = self.am.sma(self.fast_ma)
        slow_ma = self.am.sma(self.slow_ma)

        # 更新变量（UI显示用）
        self.fast_ma_value = fast_ma
        self.slow_ma_value = slow_ma

        # ---------- 交易逻辑 ----------
        if self.pos == 0:
            # 无持仓：等待金叉做多
            if fast_ma > slow_ma:
                self.buy(bar.close, self.fixed_size)
                self.write_log(f"金叉开多: fast={fast_ma:.2f}, slow={slow_ma:.2f}, price={bar.close}")

        elif self.pos > 0:
            # 持有多头：等待死叉平多
            if fast_ma < slow_ma:
                self.sell(bar.close, abs(self.pos))
                self.write_log(f"死叉平多: fast={fast_ma:.2f}, slow={slow_ma:.2f}, price={bar.close}")

        # 触发UI刷新
        self.put_event()

    def on_trade(self, trade):
        """成交回报回调"""
        # 更新持仓
        if trade.direction == Direction.LONG:
            self.pos += trade.volume
        else:
            self.pos -= trade.volume

        self.put_event()

    def on_order(self, order):
        """委托回报回调"""
        pass

    def on_stop_order(self, stop_order):
        """本地止盈止损单回报"""
        pass
