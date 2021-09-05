import datetime
import os
from socket import timeout
import datetime
import matplotlib.pyplot as plt
import pandas_ta as pta
import btalib
import pandas as pd
import json
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException
from time import sleep
from binance import ThreadedWebsocketManager

testnet_api_key = "Your testnet API key"
testnet_secret_key = 'Your testnet Secret Key'

client = Client(testnet_api_key, testnet_secret_key)

client.API_URL = 'https://testnet.binance.vision/api'

btc_usdt = "BTCUSDT"
eth_usdt = "ETHUSDT"
last_buy_price = 0.00
last_sell_price = 0.00
number_of_transactions = 0
last_transaction = "null"
asset_price = {'error': False}
bsm = ThreadedWebsocketManager()


# get all balances
def get_account_balances():
    balance = client.get_account()
    return balance


# get the balance of a particular asset
def get_account_balance(asset):
    balance = client.get_asset_balance(asset=asset)
    return balance['free']


# get the price of a particular currency pair
def get_symbol_price(symbol):
    price = client.get_symbol_ticker(symbol=symbol)
    return price['price']


def get_time_stamp(symbol, time_interval):
    time_stamp = client._get_earliest_valid_timestamp(symbol=symbol, interval=time_interval)
    return time_stamp


def get_historical_price(symbol, time_interval, time_stamp, limit):
    bars = client.get_historical_klines(symbol, time_interval, time_stamp, limit=limit)
    for line in bars:
        del line[5:]

    price_df = pd.DataFrame(bars,
                            columns=['date', 'open', 'high', 'low', 'close'])
    price_df['ema'] = price_df['close'].ewm(span=10).mean()
    price_df['rsi'] = pta.rsi(price_df['close'].astype(float), length=14)
    price_df.set_index('date', inplace=True)
    return price_df.tail(5)


# get the rsi value
def get_rsi_value(symbol, time_interval, time_stamp, limit):
    bars = client.get_historical_klines(symbol, time_interval, time_stamp, limit=limit)
    for line in bars:
        del line[5:]
        del line[:4]

    price_df = pd.DataFrame(bars, columns=['close'])
    rsi = pta.rsi(price_df['close'].astype(float), length=14)
    return float(rsi.tail(1).item())


# buy a symbol
def buy_symbol(symbol, quantity):
    try:
        buy_market = client.create_order(
            symbol=symbol,
            side='BUY',
            type='MARKET',
            quantity=quantity)

        return buy_market

    except BinanceAPIException as e:
        # error handling goes here
        print(e)
    except BinanceOrderException as e:
        # error handling goes here
        print(e)


# sell a symbol
def sell_symbol(symbol, quantity):
    try:
        sell_market = client.create_order(
            symbol=symbol,
            side='SELL',
            type='MARKET',
            quantity=quantity)

        return sell_market

    except BinanceAPIException as e:
        # error handling goes here
        print(e)
    except BinanceOrderException as e:
        # error handling goes here
        print(e)


def get_price_changes(msg):
    ''' define how to process incoming WebSocket messages '''
    if msg['e'] != 'error':
        print(msg['c'])
        asset_price['last'] = msg['c']
        asset_price['bid'] = msg['b']
        asset_price['last'] = msg['a']
        asset_price['error'] = False
    else:
        asset_price['error'] = True


def start_monitoring_prices(symbol):
    bsm.start()
    bsm.start_symbol_ticker_socket(callback=get_price_changes, symbol=symbol)


def stop_monitoring_prices():
    bsm.stop()


def print_historical_price(symbol, time_interval, timestamp, limit):
    data = get_historical_price(symbol, time_interval, timestamp, limit)

    price_df = pd.DataFrame(data,
                            columns=['date', 'open', 'high', 'low', 'close'])
    price_df.set_index('date', inplace=True)
    price_df['20sma'] = btalib.sma(price_df.close, period=20).df
    price_df.to_csv('price_bars.csv')
    print(price_df.tail(5))


# make a transaction stamp after a trade is made
def make_transaction_stamp(transaction_id, timestamp, transaction, price, income_statement, balance_btc, balance_usdt, total_balance):

    new_transaction = {
        'transaction_id': transaction_id,
        'timestamp': timestamp,
        'transaction': transaction,
        'price': price,
        'income_statement': income_statement,
        'account_balance_btc': balance_btc,
        'account_balance_usdt': balance_usdt,
        'total_balance': total_balance
    }
    with open('transactions.json', "r+") as file:
        if os.stat('transactions.json').st_size == 0:
            transactions = {'transactions': []}
            with open('transactions.json', "w") as json_file:
                json.dump(transactions, json_file, indent=4)
            transactions = json.load(file)
            transactions['transactions'].append(new_transaction.copy())
            file.seek(0)
            json.dump(transactions, file, indent=4)
        else:
            transactions = json.load(file)
            transactions['transactions'].append(new_transaction.copy())
            file.seek(0)
            json.dump(transactions, file, indent=4)


def start_trading(symbol):
    try:
        rsi = (get_rsi_value(symbol, '1m', get_time_stamp(btc_usdt, '30m'), 1000))
    except timeout:
        start_trading(btc_usdt)
    account_balance_btc = get_account_balance('BTC')
    account_balance_usdt = get_account_balance('USDT')
    global last_buy_price
    global last_sell_price
    global number_of_transactions
    global last_transaction
    print(rsi)
    if (rsi >= 70) & (last_transaction != 'sell'):
        sell_symbol(btc_usdt, account_balance_btc)
        number_of_transactions = number_of_transactions + 1
        last_transaction = 'sell'
        make_transaction_stamp(number_of_transactions, datetime.datetime.now(), 'sell', get_symbol_price(btc_usdt), last_sell_price - last_buy_price, account_balance_btc, account_balance_usdt, ((float(get_symbol_price(btc_usdt)) * float(get_account_balance('BTC'))) + float(get_account_balance('USDT'))) * float(411))
        last_sell_price = float(get_symbol_price(btc_usdt))
    elif (rsi <= 30) & (last_transaction != 'buy'):
        buy_symbol(btc_usdt, account_balance_btc)
        number_of_transactions = number_of_transactions + 1
        last_transaction = 'buy'
        make_transaction_stamp(number_of_transactions, datetime.datetime.now(), 'buy', get_symbol_price(btc_usdt), last_sell_price - last_buy_price, account_balance_btc, account_balance_usdt, ((float(get_symbol_price(btc_usdt)) * float(get_account_balance('BTC'))) + float(get_account_balance('USDT'))) * float(411))
        last_buy_price = float(get_symbol_price(btc_usdt))
    start_trading(btc_usdt)


# command to start trading a currency pair
start_trading(btc_usdt)
