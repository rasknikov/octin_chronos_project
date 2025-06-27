"""
Broker Gateway — Module 4
===========================
The only module that touches the internet.

Listens to signals from the Oracle (Module 2), applies risk management
(fixed 1% of account balance), calculates lot size, and dispatches
orders via broker API.

This is an INTERFACE STUB. Implement the broker-specific methods
for your platform (MetaTrader 5, cTrader, Binance, etc).

Usage:
    from broker_gateway import BrokerGateway

    gw = BrokerGateway(
        account_balance=10_000.0,
        risk_pct=0.01,
        pip_value=10.0,  # USD per pip per standard lot
    )

    # Receive signal from Oracle
    signal = {"signal": 1, "delta_pips": 45.2, "p_now": 1.1050}

    if signal['signal'] != 0:
        order = gw.prepare_order(
            symbol="EURUSD",
            signal=signal['signal'],
            current_price=signal['p_now'],
            stop_loss_pips=30.0,
        )
        gw.execute_order(order)
"""

import math


class BrokerGateway:
    """
    Risk management + order dispatch interface.

    The Sacred Rule: never risk more than `risk_pct` of the account
    on a single trade. The lot size is computed from the stop-loss
    distance, not the signal magnitude.
    """

    def __init__(self, account_balance: float = 10_000.0,
                 risk_pct: float = 0.01,
                 pip_value: float = 10.0,
                 max_lots: float = 5.0):
        """
        Parameters
        ----------
        account_balance : float — current account balance in account currency.
        risk_pct        : float — maximum risk per trade (0.01 = 1%).
        pip_value       : float — value per pip per standard lot in account currency.
                          For EURUSD with USD account: ~$10 per pip per lot.
        max_lots        : float — absolute maximum lot size (safety cap).
        """
        self.balance = account_balance
        self.risk_pct = risk_pct
        self.pip_value = pip_value
        self.max_lots = max_lots

    def prepare_order(self, symbol: str, signal: int,
                      current_price: float,
                      stop_loss_pips: float) -> dict:
        """
        Calculate the lot size and prepare an order.

        Parameters
        ----------
        symbol         : str — trading symbol (e.g. "EURUSD").
        signal         : int — +1 for BUY, -1 for SELL.
        current_price  : float — current market price.
        stop_loss_pips : float — distance to stop-loss in pips.

        Returns
        -------
        order : dict with all order parameters.
        """
        # Risk amount in account currency
        risk_amount = self.balance * self.risk_pct

        # Lot size from risk / (SL distance × pip value)
        if stop_loss_pips > 0 and self.pip_value > 0:
            lot_size = risk_amount / (stop_loss_pips * self.pip_value)
        else:
            lot_size = 0.01  # minimum lot

        # Apply safety cap
        lot_size = min(lot_size, self.max_lots)

        # Round to 2 decimal places (standard lot precision)
        lot_size = math.floor(lot_size * 100) / 100

        # Compute SL and TP prices
        sl_distance = stop_loss_pips * 0.0001
        if signal == 1:  # BUY
            sl_price = current_price - sl_distance
            order_type = "BUY"
        else:  # SELL
            sl_price = current_price + sl_distance
            order_type = "SELL"

        return {
            "symbol": symbol,
            "type": order_type,
            "direction": signal,
            "price": current_price,
            "lot_size": lot_size,
            "sl_price": round(sl_price, 5),
            "risk_amount": round(risk_amount, 2),
            "risk_pct": self.risk_pct,
        }

    def execute_order(self, order: dict) -> dict:
        """
        STUB — Send order to broker.

        Override this method with your broker's API:
        - MetaTrader 5: mt5.order_send(...)
        - cTrader:      ctrader_api.create_order(...)
        - Binance:      client.futures_create_order(...)

        Returns
        -------
        result : dict with execution confirmation or error.
        """
        print(f"\n  [BROKER GATEWAY] Order prepared (NOT EXECUTED — stub mode):")
        print(f"    Symbol:    {order['symbol']}")
        print(f"    Type:      {order['type']}")
        print(f"    Lot Size:  {order['lot_size']}")
        print(f"    Price:     {order['price']}")
        print(f"    Stop-Loss: {order['sl_price']}")
        print(f"    Risk:      ${order['risk_amount']} ({order['risk_pct']*100:.1f}%)")

        return {
            "status": "STUB — NOT CONNECTED TO BROKER",
            "order": order,
        }

    def update_balance(self, new_balance: float):
        """Update the account balance (call after each trade or periodically)."""
        self.balance = new_balance
