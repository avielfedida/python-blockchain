from hashlib import sha256
import json

def hash_string_256(s):
    return sha256(s).hexdigest()

def hash_block(block):
    # Encode as UTF-8 for sha("Unicode-objects must be encoded before hashing")
    # Sort keys because dictionaries are unordered.
    # Copy because we wish to override the transactions array
    cpy = block.__dict__.copy()
    cpy['transactions'] = [tx.to_ordered_dict() for tx in cpy['transactions']]
    return hash_string_256(json.dumps(cpy, sort_keys=True).encode())