from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from blockchain import Blockchain
from wallet import Wallet
from argparse import ArgumentParser

app = Flask(__name__)
CORS(app)

wallet = None
blockchain = None

@app.route('/', methods=['GET'])
def get_node_ui():
    return send_from_directory('ui', 'node.html')

@app.route('/network', methods=['GET'])
def get_network_ui():
    return send_from_directory('ui', 'network.html')


@app.route('/wallet', methods=['GET'])
def load_keys():
    if blockchain is None or wallet is None:
        return jsonify({
            'message': 'Blockchain or wallet is not initialized.'
        }), 500
    else:
        return jsonify({
            'public_key': wallet.public_key,
            'private_key': wallet.private_key,
            'funds': blockchain.get_balance()
        }), 200

@app.route('/balance/<for_pk>', methods=['GET'])
def get_balance(for_pk):
    return jsonify({
        'message': 'Fetched balance succesfully',
        'balance': blockchain.get_balance(None if for_pk == '' or for_pk == None else for_pk)    
    }), 200

@app.route('/mine', methods=['POST'])
def mine():
    if blockchain.resolve_conflicts:
        return jsonify({
            'message': 'Resolve conflicts first, block not added'
        }), 409
    block = blockchain.mine_block(wallet.public_key)
    if block:
        dict_block = block.__dict__.copy()
        dict_block['transactions'] = [tx.__dict__ for tx in dict_block['transactions']]
        return jsonify({
            'message': 'Block mined succesfully',
            'block': dict_block,
            'funds': blockchain.get_balance()
        }), 201
    else:
        return jsonify({
            'message': 'Adding a block failed.'
        }), 500

@app.route('/chain', methods=['GET'])
def get_chain():
    snapshot = blockchain.chain[:]
    dict_chain = [block.__dict__.copy() for block in snapshot]
    for dict_block in dict_chain:
        dict_block['transactions'] = [tx.__dict__ for tx in dict_block['transactions']]
    return jsonify(dict_chain), 200

@app.route('/transactions', methods=['GET'])
def get_open_transactions():
    txs = blockchain.open_transactions[:]
    return jsonify([tx.__dict__ for tx in txs]), 200

@app.route('/broadcast-transaction', methods=['POST'])
def broadcast_transaction():
    values = request.get_json()
    if not values:
        return jsonify({
            'message': 'No data found.'
        }), 400
    required = ['sender', 'recipient', 'amount', 'signature']
    if not all(key in values for key in required):
        return jsonify({
            'message': 'Required fields are missing'
        }),400
    success = blockchain.add_transaction(values['recipient'], values['sender'], values['signature'], values['amount'], is_receiving=True)
    if success:
        return jsonify({
            'message': 'Transaction broadcast.',
            'transaction': {
                'sender': values['sender'],
                'recipient': values['recipient'],
                'amount': values['amount'],
                'signature': values['signature']
            }
        }), 201
    else:
        return jsonify({
            'message': 'Broadcast transaction failed.'
        }), 500

@app.route('/transaction', methods=['POST'])
def add_transaction():
    values = request.get_json()
    if not values:
        return jsonify({
            'message': 'No data found.'
        }), 400
    required_fields = ['recipient', 'amount']
    if not all(field in values for field in required_fields):
        return jsonify({
            'message': 'Required data is missing'
        }), 400
    signature = wallet.sign_tx(wallet.public_key, values['recipient'], values['amount'])
    success = blockchain.add_transaction(values['recipient'], wallet.public_key, signature, values['amount'])
    if success:
        return jsonify({
            'message': 'Successfully added transaction.',
            'transaction': {
                'sender': wallet.public_key,
                'recipient': values['recipient'],
                'amount': values['amount'],
                'signature': signature
            },
            'funds': blockchain.get_balance()
        }), 201
    else:
        return jsonify({
            'message': 'Creating a transaction failed.'
        }), 500

@app.route('/node', methods=['POST'])
def add_node():
    values = request.get_json()
    if not values:
        return jsonify({
            'message': 'No data attached.'
        }), 400
    if 'node' not in values:
        return jsonify({
            'message': 'No node data found.'
        }), 400
    node = values['node']
    blockchain.add_peer_node(node)
    return jsonify({
        'message': 'Node added succesfully',
        'all_nodes': blockchain.get_peer_nodes()
    }), 201


@app.route('/node/<node_url>', methods=['DELETE'])
def remove_node(node_url):
    if node_url == '' or node_url == None:
        return jsonify({
            'message': 'No node found.'
        }), 400
    blockchain.remove_peer_node(node_url)
    return jsonify({
        'message': 'Node removed succesfully',
        'all_nodes': blockchain.get_peer_nodes()
    }), 200

@app.route('/resolve-conflicts', methods=['POST'])
def resolve_conflicts():
    replaced = blockchain.resolve()
    return jsonify({
        'message': 'Chain was {}.'.format('replaced.' if replaced else 'not replaced.')
    }), 200

@app.route('/nodes', methods=['GET'])
def get_nodes():
    return jsonify({
        'message': 'Succesfully retrived nodes',
        'all_nodes': blockchain.get_peer_nodes()
    }), 200


@app.route('/broadcast-block', methods=['POST'])
def broadcast_block():
    values = request.get_json()
    if not values:
        return jsonify({
            'message': 'No data found.'
        }), 400
    if 'block' not in values:
        return jsonify({
            'message': 'Required block field is missing'
        }),400
    block = values['block']
    if block['index'] == blockchain.chain[-1].index + 1:
        if blockchain.add_block(block):
            return jsonify({
                'message': 'Block added'
            }), 201
        else:
            return jsonify({
                'message': 'Received block was rejected.'
            }), 409
    elif block['index'] > blockchain.chain[-1].index:
        blockchain.resolve_conflicts = True
        return jsonify({
            'message': 'Blockchain seems to differ from local blockchain'
        }), 200
    else:
        return jsonify({
            'message': 'Blockchain seems to be shorter, block not added'
        }), 409


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    args = parser.parse_args()
    wallet = Wallet(args.port)
    blockchain = Blockchain(2, wallet.public_key, args.port)
    app.run(host='0.0.0.0', port=args.port)