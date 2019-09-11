from functools import reduce
from hashlib import sha256
import json
from collections import OrderedDict
from block import Block
from time import time
from transaction import Transaction
from utility.verification import Verification
from utility.hash_utils import hash_block
from wallet import Wallet
import requests

class Blockchain:
    def __init__(self, difficulty, public_key, node_id, reward=10):
        self.reward = reward
        self.public_key = public_key
        self.genesis = Block(0,'',[],100,0)
        self.chain = [self.genesis]
        self.node_id = node_id
        self.open_transactions = []
        self.difficulty = difficulty
        self.peer_nodes = set()
        self.resolve_conflicts = False
        self.load_data()
    
    def save_data(self):
        try:
            with open(f'blockchain-{self.node_id}.txt', mode='w') as f:
                f.write(json.dumps([block.__dict__ for block in [Block(b.index, b.previous_hash, [tx.__dict__ for tx in b.transactions], b.proof, b.timestamp) for b in self.chain]]))
                f.write('\n')
                f.write(json.dumps([tx.__dict__ for tx in self.open_transactions]))
                f.write('\n')
                f.write(json.dumps(list(self.peer_nodes)))
        except IOError:
            print('Blockchain saving failed.')
    
    def mine_block(self, node):
        proof = self.proof_of_work()
        # OrderedDict so that the order of the transactions dicrionary will always be the same.
        reward_transaction = Transaction('MINING', node, '', self.reward)
        # We copy in case our block will be deined, this way we do not override directly our open_transactions.
        copied_transactions = self.open_transactions[:]
        # Verify block transactions
        for tx in copied_transactions:
            if not Wallet.verifty_tx_sign(tx):
                return False
        copied_transactions.append(reward_transaction) # Reward miner transaction
        block = Block(len(self.chain),  hash_block(self.chain[-1]), copied_transactions, proof)
        self.chain.append(block)
        self.open_transactions = []
        self.save_data()
        converted_block = block.__dict__.copy()
        converted_block['transactions'] = [tx.__dict__ for tx in converted_block['transactions']]
        for node in self.peer_nodes:
            try:
                resp = requests.post(f'http://{node}/broadcast-block', json={
                    'block': converted_block
                })
                if resp.status_code == 400 or resp.status_code == 500:
                    print('Block declined, needs resolving')
                if resp.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                print(f'Peer {node} broadcast-block failed')
                continue
        return block

    # is_receiving == True if it's a broadcast we got.
    def add_transaction(self, recipient, sender, signature, amount=1.0, is_receiving=False):
        tx = Transaction(sender, recipient, signature, amount)
        if Verification.verify_tx(tx, self.get_balance): # Signature + Balance verification
            self.open_transactions.append(tx)
            self.save_data()
            if not is_receiving:
                for node in self.peer_nodes:
                    try:
                        resp = requests.post(f'http://{node}/broadcast-transaction', json={
                            'sender': sender,
                            'recipient': recipient,
                            'amount': amount,
                            'signature': signature
                        })
                        if resp.status_code == 400 or resp.status_code == 500:
                            print('Transaction declined, needs resolving')
                            return False
                    except requests.exceptions.ConnectionError:
                        print(f'Peer {node} broadcast-transaction failed')
                        continue
            return True
        return False

    def get_balance(self, for_pk=None):
        # We gain here an array of arrays, like [ [], [1,2] , [3,4] ]. The first is empty because it represent the genesis.
        # We return received - send + get_open_tx_balance()
        if for_pk == None:
            for_pk = self.public_key
        return sum([sum([tx.amount for tx in block.transactions if tx.recipient == for_pk]) for block in self.chain]) - sum([sum([tx.amount for tx in block.transactions if tx.sender == for_pk]) for block in self.chain]) + self.__get_open_tx_balance(for_pk)

    def __get_open_tx_balance(self, for_pk):
        return sum([tx.amount for tx in self.open_transactions if tx.recipient == for_pk]) - sum([tx.amount for tx in self.open_transactions if tx.sender == for_pk])

    def load_data(self):
        try:
            # Load saved blockchain
            with open(f'blockchain{self.node_id}.txt', mode='r') as f:
                file_content = f.readlines()
                if len(file_content) > 0:
                    self.chain = json.loads(file_content[0][:-1])  # The [:-1] is to remove the \n
                    # When we load the json it won't load as OrderedDict so...
                    self.chain = [Block(block['index'], block['previous_hash'], [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']], block['proof'], block['timestamp']) for block in self.chain]
                    # Same for open transactions
                    self.open_transactions = json.loads(file_content[1][:-1]) # The [:-1] is to remove the \n
                    self.open_transactions = [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in self.open_transactions]
                    self.peer_nodes = set(json.loads(file_content[2]))

        except (IOError, IndexError):
            print('Failed to find blockchain, generated new blockchain file.')
            self.save_data()

        if not Verification.verify_chain(self.get_balance, self.difficulty, self.chain):
            print('Invalid chain, please obtain a valid one or clear the file being used.')
            exit()
    
    def proof_of_work(self):
        proof = 0
        while not Verification.valid_proof(self.open_transactions, hash_block(self.chain[-1]), proof, self.difficulty):
            proof += 1
        return proof

    # Conflict resolution
    def resolve(self):
        winner_chain = self.chain
        replace = False
        for node in self.peer_nodes:
            try:
                resp = requests.get(f'http://{node}/chain')
                node_chain = resp.json()
                node_chain = [
                    Block(block['index'], block['previous_hash'], 
                    [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']], 
                    block['proof'], 
                    block['timestamp']) for block in node_chain]
                node_chain_length = len(node_chain)
                local_chain_length = len(self.chain)
                if node_chain_length > local_chain_length and Verification.verify_chain(self.get_balance, self.difficulty, self.chain):
                    winner_chain = node_chain
                    replace = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        self.chain = winner_chain
        if replace:
            self.open_transactions = []
        self.save_data()
        return replace

    def add_block(self, block):
        txs = [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']]
        # Check proof is correct and previous hashes matches
        # The txs[-1] is so to skip our reward tx because we calculate the proof without it.
        if not Verification.valid_proof(txs[:-1], block['previous_hash'], block['proof'], self.difficulty) or not hash_block(self.chain[-1]) == block['previous_hash']:
            return False
        self.chain.append(Block(block['index'], block['previous_hash'], txs, block['proof'], block['timestamp']))
        
        # If we got a block with some of our opentx's inside we need to remove these open tx's
        stored_txs = self.open_transactions[:]
        for itx in block['transactions']:
            for opentx in stored_txs:
                if opentx.sender == itx['sender'] and opentx.recipient == itx['recipient'] and opentx.amount == itx['amount'] and opentx.signature == itx['signature']:
                    try:
                        self.open_transactions.remove(opentx)
                    except ValueError:
                        print('Item was already removed')
        self.save_data()
        return True

    def add_peer_node(self, node):
        self.peer_nodes.add(node)
        self.save_data()

    def remove_peer_node(self, node):
        self.peer_nodes.discard(node)
        self.save_data()
    
    def get_peer_nodes(self):
        return list(self.peer_nodes)