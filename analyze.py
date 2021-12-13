import json
import os
import pymongo

import matplotlib.pyplot as plt
import pandas as pd
from pandasgui import show
from pandas.plotting import register_matplotlib_converters

MONGO_HOST = "localhost"
MONGO_PORT = 27017

mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

collection = mongo_connection["front_running-earl"]["MEV_results"]

df = pd.DataFrame(list(collection.find()))

print(df.iloc[1])


# remove 
print(len(df))
df_filtered = df[df["list_of_erc20_and_eth_transfers"].apply(lambda x: len(x)) >= 3]

print(len(df_filtered))
# df_filtered = df_filtered[:100]

# show(df_filtered)


# show(df_filtered_part["list_of_erc20_and_eth_transfers"])


from collections import defaultdict
from web3 import Web3
import json
from datetime import datetime
import requests

WEB3_WS_PROVIDER = "wss://mainnet.infura.io/ws/v3/41e2dadcce7245d986bbc9e1196ca43b"

f = open('/home/epotters/crypto/eth/Frontrunner-Jones/scripts/analysis/MEV-analysis/erc20-abi.json',)
ABI = json.load(f)

w3 = Web3(Web3.WebsocketProvider(WEB3_WS_PROVIDER))


contract_mapping = {}
contract_decimals = {}
token_price_in_usd = {}

unique_block_number = df_filtered.block_number.unique()

block_account = {}

for block_number in unique_block_number:
    transfers_of_block = df_filtered[df["block_number"] == block_number]
    tranfers=  transfers_of_block["list_of_erc20_and_eth_transfers"]

    # unix_timestamp = w3.eth.getBlock(int(block_number)).timestamp

    # block_date =  datetime.fromtimestamp(unix_timestamp).strftime('%d-%m-%Y')

    # print(len(tranfers))
    accounts_balance = defaultdict(list)

    for transfer in tranfers:
        temp_balance = defaultdict(lambda: defaultdict(int))    
        for log in transfer:
            # print(f'TO: {log["to"]} , value: {int(log["value"],16)}')
            if log["token_address"] not in contract_mapping:
                contract = w3.eth.contract(Web3.toChecksumAddress(log["token_address"]), abi=ABI)

                token_name = contract.functions.name().call()
                token_decimals = contract.functions.decimals().call()

                contract_mapping[log["token_address"]] = token_name
                contract_decimals[log["token_address"]] = token_decimals


                # Price
                # token_id_price = token_name.lower().replace(" ", "-")

                # price_url = f"https://api.coingecko.com/api/v3/coins/{token_id_price}/history?date={block_date}&localization=false"

                # response = requests.get(price_url)

                # if response.status_code != 200:
                #     print(response.text, token_name)

                    


            else:
                token_name = contract_mapping[log["token_address"]]
                token_decimals = contract_decimals[log["token_address"]]


            # Get price of asset

            
            temp_balance[log["to"]][token_name] += int(log["value"],16) / 10**token_decimals

            # print(accounts_balance)
        
        for key, item in temp_balance.items():
            accounts_balance[key].append(item)

    block_account[str(block_number)] = accounts_balance



# show(block_account)

data_frame_list = []

# Find addresss distribution
i = 0
for block in block_account:
    for address in block_account[block]:
        # data frame of address in block
        print(f"index: {i}") 
        
        df = pd.DataFrame(block_account[block][address])
        data_frame_list.append(df)

        df.boxplot()

        save_results_to = '/home/epotters/Pictures/result/second-go/'
        # plt.savefig(save_results_to + f'figure-block@{block}-address@{address}')
        plt.savefig("{0}figure-block@{1}-address@{2}".format(save_results_to, block, address))

        plt.clf()
        i += 1

        # print(df)
        # columns = list(df.columns)
        # if len(columns) == 1:
        #     # Do fboxplot
        #     plt.figure()
        #     ax1 = df.boxplot(column=columns)
        # elif len(columns) == 2:
        #     # Do scatterplot
        #     plt.figure()
        #     ax1 = df.plot.scatter(columns[0], columns[1])
        # else:
        #     pass



        
# data_frame_list[0].boxplot()

# plt.show()