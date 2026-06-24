window.VSEF_MOCK = {
  dataSources: [
    ["OHLCV", "available"],
    ["Adjusted close", "required"],
    ["Turnover", "required"],
    ["Market cap", "required"],
    ["Foreign flow", "required"],
    ["VNINDEX/VN30 index context", "required"],
    ["Sector/industry context", "required"],
    ["News/social/event context", "demo placeholder"]
  ],
  riskItems: [
    ["Data quality risk", "acceptable for demo", "Local OHLCV and duplicate checks", "review required"],
    ["Liquidity risk", "needs evidence", "Expanded local panel", "request more data"],
    ["Volatility/gap risk", "review required", "Risk V3 diagnostics", "inspect gaps"],
    ["Model disagreement risk", "review required", "Diagnostic ensemble outputs", "compare evidence"],
    ["Calibration risk", "needs evidence", "Calibration gate", "mark evidence insufficient"],
    ["Leakage/duplicate/overlap risk", "acceptable for demo", "Repair audit", "approve diagnostic wording"],
    ["Evidence staleness risk", "review required", "Evidence timestamp placeholder", "request update"],
    ["Claim-boundary risk", "blocked", "60% gate and benchmark scope", "reject broad claim"]
  ],
  socialCards: [
    "Banking sector policy context",
    "Interest rate discussion",
    "Credit growth narrative",
    "Market liquidity conditions"
  ],
  evaluationRows: [
    ["forecast-vs-actual rows", "local labeled rows", "evaluated", "coverage disclosed"],
    ["baseline comparison", "random / majority / previous-direction", "visible", "baseline dominance checked"],
    ["Wilson interval", "final holdout evaluator", "available", "uncertainty shown"],
    ["MCC", "release gate", "available", "positive MCC required"],
    ["coverage", "retained-row disclosure", "available", "low coverage blocks claims"],
    ["holdout gate", "hard 60% release gate", "blocked", "unsupported forecast claims blocked"],
    ["validation vs holdout gap", "fresh validation protocol", "review required", "overfit risk visible"],
    ["Full local run", "112,500 evaluated rows", "failed performance release", "honest negative evidence"],
    ["Performance rescue", "bounded local workflow", "validation-only", "human review required"],
    ["Data-expanded 60% attempt", "205 retained rows", "release-blocked", "insufficient rows"]
  ],
  reviewItems: [
    ["Forecast claim review", "blocked", "60% hard gate", "high", "reject broad claim"],
    ["Data quality review", "review required", "OHLCV and expanded-data gaps", "medium", "request more data"],
    ["61.61% benchmark scope review", "exact-scope only", "VN30 hourly benchmark card", "medium", "approve diagnostic wording"],
    ["60% gate failure review", "blocked", "forecast_release_blocked_below_60pct", "high", "mark evidence insufficient"],
    ["Engine-universe skip reason review", "review required", "77,730 static-only skips", "medium", "request dependency outputs"],
    ["Expanded data requirement review", "needs evidence", "real expanded data contract", "high", "request more data"]
  ],
  blockedWarnings: [
    "Do not present 61.61% as broad system-wide accuracy.",
    "Do not present the local demo as deployment-ready.",
    "Do not present evidence as market-action guidance.",
    "Do not present benchmark evidence as profitability proof."
  ],
  pitchSummary: "VSEF is a local-only AI-assisted diagnostic workspace that organizes data quality, model evidence, risk governance, bounded benchmark evidence, human review, and report generation while blocking unsupported forecast-performance claims."
};
