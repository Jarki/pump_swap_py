from dataclasses import dataclass
from typing import List, Optional
from solders.pubkey import Pubkey  # type: ignore
from solders.rpc.responses import RpcKeyedAccount  # type: ignore
from solana.rpc.commitment import Processed
from solana.rpc.types import MemcmpOpts
from construct import Padding, Struct, Int8ul, Int16ul, Int64ul, Bytes
from config import client
from constants import PF_AMM

POOL_LAYOUT = Struct(
    Padding(8),
    "pool_bump" / Int8ul,  # u8
    "index" / Int16ul,  # u16
    "creator" / Bytes(32),  # pubkey (32 bytes)
    "base_mint" / Bytes(32),  # pubkey (32 bytes)
    "quote_mint" / Bytes(32),  # pubkey (32 bytes)
    "lp_mint" / Bytes(32),  # pubkey (32 bytes)
    "pool_base_token_account" / Bytes(32),  # pubkey (32 bytes)
    "pool_quote_token_account" / Bytes(32),  # pubkey (32 bytes)
    "lp_supply" / Int64ul,  # u64
)

@dataclass
class PoolKeys:
    amm: Pubkey
    base_mint: Pubkey
    quote_mint: Pubkey
    pool_base_token_account: Pubkey
    pool_quote_token_account: Pubkey

def fetch_pool_keys(pair_address: str):
    try:
        amm = Pubkey.from_string(pair_address)
        account_info = client.get_account_info_json_parsed(amm, commitment=Processed)
        amm_data = account_info.value.data
        decoded_data = POOL_LAYOUT.parse(amm_data)

        return PoolKeys(
            amm=amm,
            base_mint=Pubkey.from_bytes(decoded_data.base_mint),
            quote_mint=Pubkey.from_bytes(decoded_data.quote_mint),
            pool_base_token_account=Pubkey.from_bytes(decoded_data.pool_base_token_account),
            pool_quote_token_account=Pubkey.from_bytes(decoded_data.pool_quote_token_account)
        )
    except:
        return None

def get_pool_reserves(pool_keys: PoolKeys):
    try:
        
        quote_vault = pool_keys.pool_quote_token_account # SOL
        base_vault = pool_keys.pool_base_token_account
        
        balances_response = client.get_multiple_accounts_json_parsed(
            [quote_vault, base_vault], 
            Processed
        )
        
        balances = balances_response.value

        quote_account = balances[0]
        base_account = balances[1]
        
        quote_account_balance = quote_account.data.parsed['info']['tokenAmount']['uiAmount']
        base_account_balance = base_account.data.parsed['info']['tokenAmount']['uiAmount']
        
        if quote_account_balance is None or base_account_balance is None:
            return None, None
        
        return base_account_balance, quote_account_balance

    except Exception as e:
        print(f"Error occurred: {e}")
        return None, None

def fetch_pair_from_rpc(base_str: str) -> Optional[str]:
    quote_str: str = "So11111111111111111111111111111111111111112"
    filters: List[List[MemcmpOpts]] = [
        [MemcmpOpts(offset=43, bytes=base_str), MemcmpOpts(offset=75, bytes=quote_str)],
        [MemcmpOpts(offset=43, bytes=quote_str), MemcmpOpts(offset=75, bytes=base_str)]
    ]
    pools: List[RpcKeyedAccount] = []
    for f in filters:
        try:
            resp = client.get_program_accounts(PF_AMM, filters=f)
            pools.extend(resp.value)
        except Exception as e:
            print(f"Error fetching program accounts with filters {f}: {e}")
            continue

    if not pools:
        return None

    best_pool_addr: Optional[str] = None
    max_liquidity: int = 0

    for pool in pools:
        try:
            pool_data: bytes = pool.account.data
            base_token_account: Pubkey = Pubkey.from_bytes(pool_data[139:171])
            quote_token_account: Pubkey = Pubkey.from_bytes(pool_data[171:203])
        except Exception as e:
            print(f"Error processing pool {pool.pubkey}: {e}")
            continue

        try:
            base_resp = client.get_token_account_balance(base_token_account)
            quote_resp = client.get_token_account_balance(quote_token_account)
        except Exception as e:
            print(f"Error fetching token account balance: {e}")
            continue

        if base_resp.value is None or quote_resp.value is None:
            continue

        try:
            base_balance: int = int(base_resp.value.amount)
            quote_balance: int = int(quote_resp.value.amount)
        except Exception as e:
            print(f"Error converting token balances to int: {e}")
            continue

        liquidity: int = base_balance * quote_balance
        if liquidity > max_liquidity:
            max_liquidity = liquidity
            best_pool_addr = str(pool.pubkey)
    return best_pool_addr

# NOT SURE IF THIS IS CORRECT
def sol_for_tokens(sol_in, pool_base, pool_quote, lp_fee_bp=20, protocol_fee_bp=5):
    user_quote_in = round(sol_in * 10000 / (10000 - protocol_fee_bp))
    protocol_fee = user_quote_in * protocol_fee_bp // 10000
    total_fee = user_quote_in * (protocol_fee_bp + lp_fee_bp) // 10000
    lp_fee = total_fee - protocol_fee
    effective_sol = sol_in - lp_fee
    k = pool_base * pool_quote
    new_quote = pool_quote + effective_sol
    new_base = k / new_quote
    tokens_out = pool_base - new_base
    return round(tokens_out)

# NOT SURE IF THIS IS CORRECT
def tokens_for_sol(token_amount, pool_base, pool_quote, lp_fee_bp=20, protocol_fee_bp=5):
    k = pool_base * pool_quote
    new_base = pool_base + token_amount
    new_quote = k / new_base
    ideal_output = pool_quote - new_quote
    lp_fee = ideal_output * (lp_fee_bp / 10000)
    protocol_fee = ideal_output * (protocol_fee_bp / 10000)
    user_quote_out = ideal_output - (lp_fee + protocol_fee)
    return round(user_quote_out, 9)
