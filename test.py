import os
import sys
import pymongo
import time
from itertools import permutations
from itertools import repeat
import bson
from web3.types import LatestBlockParam

from emulator import Emulator
from web3 import Web3

import multiprocessing
from multiprocessing import Pool


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


    w3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))
    if w3.isConnected():
        print("Connected worker to "+w3.clientVersion)
    else:
        print(colors.FAIL+"Error: Could not connect to "+WEB3_HTTP_PROVIDER+colors.END)

    mongo_connection = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)

# def analysze_transaction_order(txs, block_number):
#     print(f'txs: {txs} and block_number: {block_number}')


def chunks(l, n):
    for i in range(0, len(list(l)), n):
        yield l[i:i + n]

def analysze_transaction_batch(list_of_txs, block_data):
    print(f'Anayszing Batch')

    ########################################## 
    # Set up mongoDB client
    mongo_connection_internal = pymongo.MongoClient("mongodb://"+MONGO_HOST+":"+str(MONGO_PORT), maxPoolSize=None)
    ##########################################

    findings = []

    emu = Emulator(WEB3_HTTP_RPC_HOST, WEB3_HTTP_RPC_PORT, block_data)

    block_number = block_data["number"] + 1

    for txs in list_of_txs:
        
        emu.take_snapshot()

        finding = analysze_transaction_order(txs, emu, block_number)


        findings.append(finding)

        emu.restore_from_snapshot()


    collection = mongo_connection_internal["front_running"]["MEV_results"]
    collection.insert_many(findings)

    print(f'Finished Batch')




def analysze_transaction_order(txs, emu, block_number):

    start = time.time()

    transaction_list = []

    list_of_erc20_and_eth_transfers = []



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
                # don't know why this is not making 8-byte int to Long
                # _value = bson.Int64(int(log[2].hex(), 16))
                _value = hex(int(log[2].hex(), 16))

                list_of_erc20_and_eth_transfers.append({"token_address": token_address, "from":_from, "to":_to , "value":_value })

    # save in MongoDB database

    end = time.time()
    # print(f'Execution_time analysze_transaction_orderanalysze_transaction_order: {end-start}')
    finding = {
        "block_number": block_number,
        "transaction_hash_list": [ tx["hash"].hex() for tx in txs],
        "list_of_erc20_and_eth_transfers": list_of_erc20_and_eth_transfers,
        "execution_time": float(end-start)
    }

    return finding

    # print(f'Findings: {finding}')


    







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
            txs_permutations = list(permutations(txs,2))
            
            block_data = w3.eth.getBlock(block_number - 1, False)



            chucks_txs_permutations = chunks(txs_permutations, len(txs_permutations)//16)

            with Pool(processes=multiprocessing.cpu_count()) as pool:
                pool.starmap(analysze_transaction_batch, zip(chucks_txs_permutations, repeat(block_data)))

            # for chuck_txs_permutations in chucks_txs_permutations:
            #     analysze_transaction_batch(chuck_txs_permutations, block_data)

            end = time.time()
            print(f'Execution_time block@{block_number}: {end-start}')

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


