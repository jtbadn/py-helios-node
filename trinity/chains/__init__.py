# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseManager,
    BaseProxy,
)
import os

from evm import MainnetChain
from evm.chains.mainnet import (
    MAINNET_GENESIS_HEADER,
    MAINNET_NETWORK_ID,
)
from evm.db.backends.base import BaseDB
from evm.db.chain import AsyncChainDB
from evm.exceptions import CanonicalHeadNotFound

from p2p import ecies

from trinity.exceptions import (
    MissingPath,
)
from trinity.config import ChainConfig
from trinity.db.base import DBProxy
from trinity.db.chain import ChainDBProxy
from trinity.db.chain_head import (
    ChainHeadDBProxy,
    AsyncChainHeadDB,
)
#from trinity.db.header import (
#    AsyncHeaderDB,
#    AsyncHeaderDBProxy,
#)
from trinity.utils.mp import (
    async_method,
)
from trinity.utils.xdg import (
    is_under_xdg_trinity_root,
)

from dev_tools import (
    create_dev_test_random_blockchain_database        
)
import logging

from trinity.dev_tools import (
    MAINNET_GENESIS_HEADER,
    MAINNET_GENESIS_PARAMS,
    MAINNET_GENESIS_STATE,
    SENDER,
    RECEIVER,
)

#from .header import (
#    AsyncHeaderChain,
#    AsyncHeaderChainProxy,
#)


def is_data_dir_initialized(chain_config: ChainConfig) -> bool:
    """
    - base dir exists
    - chain data-dir exists
    - nodekey exists and is non-empty
    - canonical chain head in db
    """
    if not os.path.exists(chain_config.data_dir):
        return False

    if not os.path.exists(chain_config.database_dir):
        return False

    if not chain_config.logfile_path.parent.exists():
        return False
    elif not chain_config.logfile_path.exists():
        return False

    if chain_config.nodekey_path is None:
        # has an explicitely defined nodekey
        pass
    elif not os.path.exists(chain_config.nodekey_path):
        return False

    if chain_config.nodekey is None:
        return False

    return True


def is_database_initialized(chaindb: AsyncChainDB) -> bool:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # empty chain database
        return False
    else:
        return True


def initialize_data_dir(chain_config: ChainConfig) -> None:
    if not chain_config.data_dir.exists() and is_under_xdg_trinity_root(chain_config.data_dir):
        chain_config.data_dir.mkdir(parents=True, exist_ok=True)
    elif not chain_config.data_dir.exists():
        # we don't lazily create the base dir for non-default base directories.
        raise MissingPath(
            "The base chain directory provided does not exist: `{0}`".format(
                chain_config.data_dir,
            ),
            chain_config.data_dir
        )

    # Logfile
    if (not chain_config.logfile_path.exists() and
            is_under_xdg_trinity_root(chain_config.logfile_path)):

        chain_config.logfile_path.parent.mkdir(parents=True, exist_ok=True)
        chain_config.logfile_path.touch()
    elif not chain_config.logfile_path.exists():
        # we don't lazily create the base dir for non-default base directories.
        raise MissingPath(
            "The base logging directory provided does not exist: `{0}`".format(
                chain_config.logfile_path,
            ),
            chain_config.logfile_path
        )

    # Chain data-dir
    os.makedirs(chain_config.database_dir, exist_ok=True)

    # Nodekey
    if chain_config.nodekey is None:
        nodekey = ecies.generate_privkey()
        with open(chain_config.nodekey_path, 'wb') as nodekey_file:
            nodekey_file.write(nodekey.to_bytes())


def initialize_database(chain_config: ChainConfig, chaindb: AsyncChainDB) -> None:
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        if chain_config.network_id == MAINNET_NETWORK_ID:
            chaindb.persist_header(MAINNET_GENESIS_HEADER)
        else:
            # TODO: add genesis data to ChainConfig and if it's present, use it
            # here to initialize the chain.
            raise NotImplementedError(
                "Only the mainnet and ropsten chains are currently supported"
            )


def serve_chaindb(chain_config: ChainConfig, base_db: BaseDB) -> None:
    chaindb = AsyncChainDB(base_db, chain_config.node_wallet_address)
    chain_head_db = AsyncChainHeadDB.load_from_saved_root_hash(base_db)
        
    if not is_database_initialized(chaindb):
        if int(os.environ["INSTANCE_NUMBER"]) == 0:
            #this is for testing, we neeed to build an initial blockchain database
            create_dev_test_random_blockchain_database(base_db)
        
    if chain_config.network_id == MAINNET_NETWORK_ID:
        chain_class = MainnetChain  # type: ignore
    else:
        raise NotImplementedError(
            "Only the mainnet and ropsten chains are currently supported"
        )
    
    
    chain = chain_class(base_db, chain_config.node_wallet_address, chain_config.node_private_helios_key)  # type: ignore
        
    chain.chain_head_db.root_hash
    #headerdb = AsyncHeaderDB(base_db)
    #header_chain = AsyncHeaderChain(base_db)

    class DBManager(BaseManager):
        pass

    # Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
    # https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
    DBManager.register('get_db', callable=lambda: base_db, proxytype=DBProxy)  # type: ignore

    DBManager.register(  # type: ignore
        'get_chaindb',
        callable=lambda: chaindb,
        proxytype=ChainDBProxy,
    )
    DBManager.register('get_chain', callable=lambda: chain, proxytype=ChainProxy)  # type: ignore

    DBManager.register(  # type: ignore
        'get_chain_head_db',
        callable=lambda: chain_head_db,
        proxytype=ChainHeadDBProxy,
    )
#    DBManager.register(  # type: ignore
#        'get_headerdb',
#        callable=lambda: headerdb,
#        proxytype=AsyncHeaderDBProxy,
#    )
#    DBManager.register(  # type: ignore
#        'get_header_chain',
#        callable=lambda: header_chain,
#        proxytype=AsyncHeaderChainProxy,
#    )

    manager = DBManager(address=str(chain_config.database_ipc_path))  # type: ignore
    server = manager.get_server()  # type: ignore

    server.serve_forever()  # type: ignore


class ChainProxy(BaseProxy):
    coro_import_block = async_method('import_block')
