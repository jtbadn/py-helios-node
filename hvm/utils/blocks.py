import rlp_cython as rlp

from eth_keys import keys
from eth_keys.exceptions import (
    BadSignature,
)

from hvm.exceptions import (
    ValidationError,
)
from hvm.utils.numeric import (
    is_even,
    int_to_big_endian,
)

from hvm.rlp.headers import (
    BaseBlockHeader,
)

from eth_utils import from_wei, to_wei

from typing import (
    List,
    TYPE_CHECKING
)
if TYPE_CHECKING:
    from hvm.rlp.blocks import BaseBlock


EIP155_CHAIN_ID_OFFSET = 35
V_OFFSET = 27


def is_eip_155_signed_block_header(block_header: BaseBlockHeader) -> bool:
    if block_header.v >= EIP155_CHAIN_ID_OFFSET:
        return True
    else:
        return False


def extract_chain_id(v: int) -> int:
    if is_even(v):
        return (v - EIP155_CHAIN_ID_OFFSET - 1) // 2
    else:
        return (v - EIP155_CHAIN_ID_OFFSET) // 2


def extract_signature_v(v: int) -> int:
    if is_even(v):
        return V_OFFSET + 1
    else:
        return V_OFFSET

# def get_message_from_block_header(block_header: BaseBlockHeader, chain_id:int = None) -> bytes:
#     if chain_id is None:
#         chain_id = block_header.chain_id
#
#     header_parts = rlp.decode(rlp.encode(block_header, sedes = block_header.__class__), use_list=True)
#     header_parts_for_signature = (
#             header_parts[:3] + [header_parts[5]] + header_parts[8:11] + [header_parts[12]] + [int_to_big_endian(chain_id), b'', b'']
#     )
#     message = rlp.encode(header_parts_for_signature)
#     return message


def create_block_header_signature(block_header: BaseBlockHeader, private_key, chain_id):
    message = block_header.get_message_for_signing(chain_id)
    
    signature = private_key.sign_msg(message)

    canonical_v, r, s = signature.vrs

    v = canonical_v + chain_id * 2 + EIP155_CHAIN_ID_OFFSET

    return v, r, s


def validate_block_header_signature(block_header: BaseBlockHeader) -> None:
    v = extract_signature_v(block_header.v)

    canonical_v = v - 27

    vrs = (canonical_v, block_header.r, block_header.s)
    signature = keys.Signature(vrs=vrs)

    message = block_header.get_message_for_signing()
    
    try:
        public_key = signature.recover_public_key_from_msg(message)
    except BadSignature as e:
        raise ValidationError("Bad Signature: {0}".format(str(e)))

    if not signature.verify_msg(message, public_key):
        raise ValidationError("Invalid Signature")


def extract_block_header_sender(block_header: BaseBlockHeader) -> bytes:
    if is_even(block_header.v):
        v = 28
    else:
        v = 27

    r, s = block_header.r, block_header.s

    canonical_v = v - 27
    vrs = (canonical_v, r, s)
    signature = keys.Signature(vrs=vrs)

    message = block_header.get_message_for_signing()
    
    public_key = signature.recover_public_key_from_msg(message)
    sender = public_key.to_canonical_address()
    return sender



def get_block_average_transaction_gas_price(block):
    #Always accept blocks with just receive or reward tx.
    if len(block.transactions) == 0:
        return float('inf')

    total_sum = 0
    num_tx = 0
    for transaction in block.transactions:
        num_tx += 1
        total_sum += transaction.gas_price
        
    average = int(total_sum/num_tx)
    return average
        



def does_block_meet_min_gas_price(block, chain):
    average_gas_price_in_wei = get_block_average_transaction_gas_price(block) #in wei
    required_min_gas_price_in_gwei = chain.chaindb.get_required_block_min_gas_price(block.header.timestamp) #in gwei

    if average_gas_price_in_wei == float('inf'):
        return True

    average_gas_price_in_gwei = from_wei(average_gas_price_in_wei, 'gwei')

    if average_gas_price_in_gwei < required_min_gas_price_in_gwei:
        return False
    else:
        return True

# def reorganize_chronological_block_list_for_correct_chronological_order_at_index(self, block_list: List['BaseBlock'],
#                                                                                  index: int) -> List['BaseBlock']:
#     '''
#     This takes the block at the given index, and moves it to the back of the list of any blocks with the same timestamp.
#     '''
#     # Check if we are at the end of the list. If so, there couldnt possibly be any parents further down.
#     if index + 1 >= len(block_list):
#         return block_list
#
#     # First, get all of this block's dependencies
#     initial_block = block_list[index]
#     timestamp_of_initial_block = initial_block.header.timestamp
#
#     greatest_index_with_same_timestamp = index
#     for i in range(index + 1, len(block_list), 1):
#         block = block_list[i]
#         if block.header.timestamp > timestamp_of_initial_block:
#             break
#         greatest_index_with_same_timestamp = i
#
#     if greatest_index_with_same_timestamp == index:
#         # None were found
#         return block_list
#
#     self.logger.debug("Found that the blocks were out of order")
#     block_list.pop(index)
#     block_list.insert(greatest_index_with_same_timestamp, initial_block)
#     return block_list


def reorganize_chronological_block_list_for_correct_chronological_order_at_index(block_list: List['BaseBlock'], index:int, logger = None) -> List['BaseBlock']:
    '''
    This takes the block at the given index, and moves it to the back of the list of any blocks with the same timestamp.
    '''
    # Check if we are at the end of the list. If so, there couldnt possibly be any parents further down.
    if index + 1 >= len(block_list):
        return block_list

    # First, get all of this block's dependencies
    initial_block = block_list[index]
    timestamp_of_initial_block = initial_block.header.timestamp

    greatest_index_with_same_timestamp = index
    for i in range(index+1, len(block_list), 1):
        block = block_list[i]
        if block.header.timestamp > timestamp_of_initial_block:
            break
        greatest_index_with_same_timestamp = i

    if greatest_index_with_same_timestamp == index:
        # None were found
        return block_list

    if logger is not None:
        logger.debug("Found that the blocks were out of order")
    block_list.pop(index)
    block_list.insert(greatest_index_with_same_timestamp, initial_block)
    return block_list
