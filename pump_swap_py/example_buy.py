from pump_swap import buy
from pool_utils import fetch_pair_from_rpc

mint = "pump_swap_address"
sol_in = .01
slippage = 10
pair_address = fetch_pair_from_rpc(mint)
if pair_address:
    buy(pair_address, sol_in, slippage)
else:
    print("No pair address found...")
