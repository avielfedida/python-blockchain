from Cryptodome.PublicKey import RSA
import Cryptodome.Random as rand
from Cryptodome.Hash import SHA256
import binascii
from Cryptodome.Signature import PKCS1_v1_5

# There is no verification for the keys when loaded!
class Wallet:
    def __init__(self, node_id):
        self.node_id = node_id
        self.load_keys()

    def save_keys(self):
        with open(f'wallet-{self.node_id}.txt', mode='w') as f:
            f.write(self.public_key)
            f.write('\n')
            f.write(self.private_key)

    def load_keys(self):
        try:
            with open(f'wallet-{self.node_id}.txt', mode='r') as f:
                keys = f.readlines()
                self.public_key, self.private_key = keys[0][:-1], keys[1] # The [:-1] is to skip the \n
        except (IOError, IndexError):
            self.private_key, self.public_key = self.generate_keys()
            self.public_key = self.public_key
            self.save_keys()
            print('Failed to find wallet, generated new wallet file.')

    def generate_keys(self):
        private_key = RSA.generate(1024, rand.new().read)
        return (
            binascii.hexlify(private_key.exportKey(format='DER')).decode('ascii'),
            binascii.hexlify(private_key.publickey().exportKey(format='DER')).decode('ascii'),
        )
    
    def sign_tx(self, sender, recipient, amount):
        signer = PKCS1_v1_5.new(RSA.importKey(binascii.unhexlify(self.private_key)))
        h = SHA256.new((str(sender) + str(recipient) + str(amount)).encode('utf8'))
        signature = signer.sign(h)
        return binascii.hexlify(signature).decode('ascii')

    @staticmethod
    def verifty_tx_sign(tx):
        public_key = RSA.importKey(binascii.unhexlify(tx.sender))
        verifier = PKCS1_v1_5.new(public_key)
        h = SHA256.new((str(tx.sender) + str(tx.recipient) + str(tx.amount)).encode('utf8'))
        return verifier.verify(h, binascii.unhexlify(tx.signature))