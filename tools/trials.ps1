# Trials 2 and 3, at the paper's operating cutoff only.
#
# The brief (section 5) asks for 3-5 trials with mean/variance. Temperature 0
# does not make the answer+judge stage deterministic, so the variance is real
# and worth measuring -- but re-running the top_10 curve three times adds cost
# without adding information, because the top_10 result is a sensitivity check,
# not a headline claim. Trials 2-3 therefore sweep only top_200, and the report
# says so.
#
# Ingest is reused; only answer + judge are repeated.
#
# Run from the repository root:
#     .\tools\trials.ps1
$ErrorActionPreference = "Continue"
$py = ".\.venv\Scripts\python.exe"

foreach ($trial in 2, 3) {
    & $py -m src.run --backend mem0 --infer 1 --conversations 0 --limit 120 --cutoffs 200 --trial $trial --stage eval *> "results\v2_ext_t$trial.log"
    & $py -m src.run --backend mem0 --infer 0 --conversations 0 --limit 120 --cutoffs 200 --trial $trial --stage eval *> "results\v2_raw_t$trial.log"
}

Write-Output "[trials] trials 2 and 3 finished"
