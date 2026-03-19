"""
deploy_subscription.py — Deploy do WEbdEXSubscription na Polygon Mainnet
Uso: python deploy_subscription.py

Requer:
  pip install web3 py-solc-x
  DEPLOY_PRIVATE_KEY no ambiente ou hardcoded abaixo (NUNCA commitar)
"""
import os, json
from web3 import Web3
from solcx import compile_source, install_solc

# ── Config ────────────────────────────────────────────────────────────────────
RPC_URL      = os.getenv("RPC_URL", "https://polygon-rpc.com")  # Use RPC público como fallback — NUNCA hardcode chave Alchemy aqui
PRIVATE_KEY  = os.getenv("DEPLOY_PRIVATE_KEY", "")   # ← preencher via env, nunca hardcoded
DEPLOY_WALLET = "0xb5Fb0CDaab5784cBE05CcB9D843DaFe4663883C5"

assert PRIVATE_KEY, "Defina DEPLOY_PRIVATE_KEY no ambiente antes de rodar."

# ── Conecta ───────────────────────────────────────────────────────────────────
w3 = Web3(Web3.HTTPProvider(RPC_URL))
assert w3.is_connected(), "Sem conexão com a Polygon"
print(f"[deploy] Conectado à Polygon. Bloco atual: {w3.eth.block_number}")

bal = w3.eth.get_balance(Web3.to_checksum_address(DEPLOY_WALLET))
print(f"[deploy] Saldo da deploy wallet: {w3.from_wei(bal, 'ether'):.4f} MATIC")
assert bal > 0, "Deploy wallet sem MATIC para gas!"

# ── Compila ───────────────────────────────────────────────────────────────────
print("[deploy] Instalando solc 0.8.20...")
install_solc("0.8.20")

SOL_SOURCE = open(os.path.join(os.path.dirname(__file__), "WEbdEXSubscription.sol")).read()

compiled = compile_source(
    SOL_SOURCE,
    output_values=["abi", "bin"],
    solc_version="0.8.20",
)
contract_id  = "<stdin>:WEbdEXSubscription"
contract_ifc = compiled[contract_id]
abi      = contract_ifc["abi"]
bytecode = contract_ifc["bin"]
print(f"[deploy] Compilado OK. Bytecode: {len(bytecode)//2} bytes")

# ── Salva ABI ─────────────────────────────────────────────────────────────────
abi_path = os.path.join(os.path.dirname(__file__), "WEbdEXSubscription.abi.json")
with open(abi_path, "w") as f:
    json.dump(abi, f, indent=2)
print(f"[deploy] ABI salva em {abi_path}")

# ── Deploy ────────────────────────────────────────────────────────────────────
account  = w3.eth.account.from_key(PRIVATE_KEY)
nonce    = w3.eth.get_transaction_count(account.address)
Contract = w3.eth.contract(abi=abi, bytecode=bytecode)

tx = Contract.constructor().build_transaction({
    "from":     account.address,
    "nonce":    nonce,
    "gas":      800_000,
    "gasPrice": w3.to_wei("200", "gwei"),
    "chainId":  137,  # Polygon Mainnet
})

signed = account.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
print(f"[deploy] Tx enviada: {tx_hash.hex()}")
print("[deploy] Aguardando confirmação...")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
contract_address = receipt["contractAddress"]

print(f"\n{'='*60}")
print(f"✅ CONTRATO DEPLOYADO COM SUCESSO!")
print(f"   Endereço : {contract_address}")
print(f"   Tx hash  : {tx_hash.hex()}")
print(f"   Gas usado: {receipt['gasUsed']:,}")
print(f"   PolygonScan: https://polygonscan.com/address/{contract_address}")
print(f"{'='*60}\n")

# Salva endereço
addr_path = os.path.join(os.path.dirname(__file__), "WEbdEXSubscription.address.txt")
with open(addr_path, "w") as f:
    f.write(contract_address)
print(f"[deploy] Endereço salvo em {addr_path}")
