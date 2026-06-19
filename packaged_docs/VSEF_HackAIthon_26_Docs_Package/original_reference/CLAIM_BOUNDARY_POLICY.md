# Claim Boundary Policy

All forecast research artifacts must preserve this boundary:

- offline diagnostic only
- no trading
- no profitability claim
- no BUY/SELL
- no recommendation or investment advice
- no live deployment
- no production
- no daily T+1 operation
- final rows scoring-only
- future-blind validation-only selection required

Configured indices are index instruments, not stocks. VN100 must not be assumed
unless explicitly configured and locally available. A champion must not be
replaced without explicit future-blind evidence.

Reusable wording is defined in `src/governance/claim_boundary.py`.
