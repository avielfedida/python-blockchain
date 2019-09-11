from utility.hash_utils import hash_block, hash_string_256
from wallet import Wallet

class Verification:

    @staticmethod
    def valid_proof(transactions, last_hash, proof, difficulty):
        return hash_string_256((str([tx.to_ordered_dict() for tx in transactions]) + str(last_hash) + str(proof)).encode())[:difficulty]==difficulty*'0'

    @classmethod
    def verify_chain(cls, get_balance, difficulty, chain):
        chain_copy = chain[:]
        for idx, block in enumerate(chain_copy):
            if idx > 0:
                if block.previous_hash != hash_block(chain_copy[idx-1]):
                    return False
                if not cls.valid_proof(block.transactions[:-1], block.previous_hash, block.proof, difficulty):
                    return False
                if not all([Verification.verify_tx(tx, get_balance) for tx in block.transactions[:-1]]):
                    return False
        return True

    @staticmethod
    def verify_tx(tx, get_balance):
        return get_balance(tx.sender) >= tx.amount and Wallet.verifty_tx_sign(tx)
        