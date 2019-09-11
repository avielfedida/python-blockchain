from time import time

class Block:
    def __init__(self, index, previous_hash, transactions, proof, timestamp=None):
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.proof = proof
        self.timestamp = time() if timestamp is None else timestamp

    def __repr__(self):
        return f'Index: {self.index}, Previous hash: {self.previous_hash}, Proof: {self.proof}, Timestamp: {self.timestamp}, Transactions: {self.transactions}'