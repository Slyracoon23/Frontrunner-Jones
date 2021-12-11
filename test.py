import os
import sys
import pymongo
import time
from itertools import permutations

from emulator import Emulator
from web3 import Web3


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from utils.settings import *
from utils.utils import colors, get_prices, get_one_eth_to_usd, request_debug_trace

from eth_utils import to_canonical_address, decode_hex, encode_hex

BLOCK_NUMBER = 10995886

ERC20_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" # ERC-20 transfer event
ETH_TRANSFER = "0x" # ETH transfer bytecode
ERC20_TRANSFER_METHOD_ID = "0xa9059cbb"

def init_w3():
    global w3
    global mongo_connection


    w3 = Web3(Web3.WebsocketProvider(WEB3_WS_PROVIDER))
    if w3.isConnected():
        print("Connected worker to "+w3.clientVersion)
    else:
        print(colors.FAIL+"Error: Could not connect to "+WEB3_WS_PROVIDER+colors.END)

    mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)



def analysze_transaction_order(txs, block_number):
    start = time.time()

    transaction_list = []

    list_of_erc20_and_eth_transfers = []


    emu = Emulator(WEB3_HTTP_RPC_HOST, WEB3_HTTP_RPC_PORT, w3.eth.getBlock(block_number - 1, False))


    # Execute transaction 

    for tx in txs:
        result, executed_step = emu.send_transaction(tx)
        transaction_list.append((result,executed_step))

    
    # Find logs of transactions and find data value of transfer e.g What coin was swapped?

    for transaction in transaction_list:
        transaction = transaction[0]

        logs = transaction.get_log_entries()

        for log in logs:
            if hex(log[1][0]) == ERC20_TRANSFER:
                token_address = '0x' + log[0].hex()
                _from = hex(log[1][1])
                _to = hex(log[1][2])

                list_of_erc20_and_eth_transfers.append((token_address, _from, _to))

    # save in MongoDB database

    end = time.time()
    print(f'Execution_time analysze_transaction_orderanalysze_transaction_order: {end-start}')
    finding = {
        "block_number": block_number,
        "transaction_list": transaction_list,
        "list_of_erc20_and_eth_transfers": list_of_erc20_and_eth_transfers,
        "execution_time": end-start
    }

    collection = mongo_connection["front_running"]["MEV_results"]
    collection.insert_one(finding)







def analysze_block_range(block_range):
    

    for block_number in block_range:
            start = time.time()

            print("Analyzing block number: "+str(block_number))

            status = mongo_connection["front_running"]["MEV_status"].find_one({"block_number": block_number})
            if status:
                print("Block "+str(block_number)+" already analyzed!")
                continue

        
            block = w3.eth.getBlock(block_number, True)
            
            # get list of transactions
            txs = block["transactions"]

            # filter for transaction that are simple erc20 transfer and eth transfer
            # NO MEV can happen on those transaction only jacked up gas price
            
            def is_simple_erc20_transfer(tx):
                method_id = tx["input"][:10]
                if method_id == ERC20_TRANSFER_METHOD_ID:
                    return True
                else:
                    return False

            def is_eth_transfer(tx):
                if tx["input"] == ETH_TRANSFER:
                     return True
                else:
                    return False



            # filter eth ransactions
            # filterFalse() in itertools
            txs = filter(lambda tx: is_eth_transfer(tx) == False, txs )
            # filter transaction for single erc20 transfers
            txs = list(filter(lambda tx: is_simple_erc20_transfer(tx) == False, txs))

            # permutate over all possiblities
            txs_permutations = permutations(txs)
            for perm_txs in list(txs_permutations):
                analysze_transaction_order(perm_txs, block_number)

            end = time.time()
            print()
            collection = mongo_connection["front_running"]["MEV_status"]
            collection.insert_one({"block_number": block_number, "execution_time": end-start})




            
        




            


if __name__ == "__main__":
    init_w3()

    analysze_block_range([BLOCK_NUMBER])

    # # get block
    # block = w3.eth.getBlock(BLOCK_NUMBER, True)

    # txs = block["transactions"]

    # emu = Emulator(WEB3_HTTP_RPC_HOST, WEB3_HTTP_RPC_PORT, w3.eth.getBlock(BLOCK_NUMBER - 1, False))

    # # emu.take_snapshot()

    # transaction_list = []

    # list_of_erc20_transfers = []

    # list_of_eth_transfers = []
    
    # # old_balance = emu._evm.get_balance(to_canonical_address(list_of_address_in_block[7]))

    # # result, executed_step = emu.send_transaction(txs[7])
    # # Last account is miner address?
    # # print(emu._evm.get_accounts())

    # ## Filter for single ether transfers and single token transfers

    # # use get_accounts() EVM 
    # for tx in txs:
    #     result, executed_step = emu.send_transaction(tx)
    #     transaction_list.append((result,executed_step))

    # # Find logs of transactions and find data value of transfer e.g What coin was swapped?

    # for transaction in transaction_list:
    #     transaction = transaction[0]

    #     logs = transaction.get_log_entries()

    #     for log in logs:
    #         if hex(log[1][0]) == ERC20_TRANSFER:
    #             token_address = '0x' + log[0].hex()
    #             _from = hex(log[1][1])
    #             _to = hex(log[1][2])

    #             list_of_erc20_transfers.append((token_address, _from, _to))

    # # find eth transfers
    # for tx in txs:
    #     if tx["input"] == ETH_TRANSFER:
    #         _token = "ETH"
    #         _from = tx["from"]
    #         _to = tx["to"]

    #         list_of_eth_transfers.append((_token, _from, _to))

    




    # # if hex(transaction_list[0][0].get_log_entries()[0][1][0]) i.e. Topic is "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef" it is a transfer function



    # # new_balance = emu._evm.get_balance(to_canonical_address(list_of_address_in_block[7]))
    # accounts = emu._evm.get_accounts()
    # print(accounts)



    # # print(f'''Old Balance: {old_balance}, new Balance: {new_balance}, diff:{new_balance - old_balance}''')


