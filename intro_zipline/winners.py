# Copyright 2022 QuantRocket LLC - All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import zipline.api as algo
from zipline.pipeline import Pipeline
from zipline.pipeline.factors import AverageDollarVolume, Returns
from zipline.finance.execution import MarketOrder

MOMENTUM_WINDOW = 252

def initialize(context):
    """
    Called once at the start of a backtest, and once per day in
    live trading.
    """
    # Attach the pipeline to the algo
    algo.attach_pipeline(make_pipeline(), 'pipeline')

    algo.set_benchmark(algo.sid('FIBBG000BDTBL9'))

    # Rebalance every day, 30 minutes before market close.
    algo.schedule_function(
        rebalance,
        algo.date_rules.every_day(),
        algo.time_rules.market_close(minutes=30),
    )

def make_pipeline():
    """
    Create a pipeline that filters by dollar volume and
    calculates return.
    """
    pipeline = Pipeline(
        columns={
            "returns": Returns(window_length=MOMENTUM_WINDOW),
        },
        screen=AverageDollarVolume(window_length=30) > 10e6
    )
    return pipeline

def before_trading_start(context, data):
    """
    Called every day before market open.
    """
    factors = algo.pipeline_output('pipeline')

    # Get the top 3 stocks by return
    returns = factors["returns"].sort_values(ascending=False)
    context.winners = returns.index[:3]

def rebalance(context, data):
    """
    Execute orders according to our schedule_function() timing.
    """

    # calculate intraday returns for our winners
    current_prices = data.current(context.winners, "price")
    prior_closes = data.history(context.winners, "close", 2, "1d").iloc[0]
    intraday_returns = (current_prices - prior_closes) / prior_closes

    positions = context.portfolio.positions

    # Exit positions we no longer want to hold
    for asset, position in positions.items():
        if asset not in context.winners:
            algo.order_target_value(asset, 0, style=MarketOrder())

    # Enter long positions
    for asset in context.winners:

        # if already long, nothing to do
        if asset in positions:
            continue

        # if the stock is up for the day, don't enter
        if intraday_returns[asset] > 0:
            continue

        # otherwise, buy a fixed $100K position per asset
        algo.order_target_value(asset, 100e3, style=MarketOrder())
