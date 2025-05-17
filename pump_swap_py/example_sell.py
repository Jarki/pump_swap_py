from pump_swap import sell
from pool_utils import fetch_pair_from_rpc

mint = "pump_swap_address"
percentage = 100
slippage = 5
pair_address = fetch_pair_from_rpc(mint)
if pair_address:
    sell(pair_address, percentage, slippage)
else:
    print("No pair address found...")
