# Re-run the answer + judge stage after the prompt-fidelity fix in
# src/prompts.py::_human_date (README debug diary, row 9).
#
# Ingest is deliberately NOT repeated: the vector stores are unchanged. Only the
# date prefix rendered into the answer prompt changed, and that is applied at
# answer time -- so re-embedding 419 turns would cost 30 minutes for nothing.
#
# Scope is raised from 40 to 120 questions so that every category the paper
# reports is actually exercised:
#     limit  40 -> multi-hop 15, temporal 20, open-domain  5, single-hop  0
#     limit 120 -> multi-hop 32, temporal 37, open-domain 13, single-hop 38
# The single-hop block simply starts later in conversation 0, which is why the
# 40-question run could not report that row at all.
#
# Run from the repository root:
#     .\tools\rerun_v2.ps1
$ErrorActionPreference = "Continue"
$py = ".\.venv\Scripts\python.exe"

& $py -m src.run --backend mem0 --infer 1 --conversations 0 --limit 120 --stage eval *> results\v2_mem0_ext.log
& $py -m src.run --backend mem0 --infer 0 --conversations 0 --limit 120 --stage eval *> results\v2_mem0_raw.log
& $py -m src.run --backend fullctx --conversations 0 --limit 120 --cutoffs 200 --stage eval *> results\v2_fullctx.log

Write-Output "[rerun] all three configurations finished"
