# Regenerate the whole evaluation corpus with Windows speech synthesis.
#   powershell -ExecutionPolicy Bypass -File scripts/make_test_audio.ps1
#
# The clips are committed so the numbers in README.md can be reproduced without
# Windows. This script exists to change or extend the corpus.
#
# Synthetic speech is a weaker test than human speech. Replace these with real
# recordings before trusting the numbers for a production decision.

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    16000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono)
$dir = Join-Path $PSScriptRoot "..\eval\audio"
New-Item -ItemType Directory -Force $dir | Out-Null
$synth.Rate = -1

function Write-Clips($clips) {
    foreach ($name in $clips.Keys) {
        $synth.SetOutputToWaveFile((Join-Path $dir "$name.wav"), $format)
        $synth.Speak($clips[$name])
        Write-Host "  $name.wav"
    }
}

# --- Speaker one: jargon clips ------------------------------------------------
Write-Host "David - jargon clips"
Write-Clips ([ordered]@{
    "j1"     = "the Quantex pipeline feeds Halberd every morning"
    "j2"     = "C R I M S flagged three exceptions in the Nimbus tier"
    "j3"     = "we migrated Vectrabridge onto the Skylark platform"
    "j4"     = "Orbex reconciliation runs before the C R I M S batch"
    "arr"    = "our A R R grew twelve percent this quarter"
    "ebitda" = "the E B I T D A margin improved significantly"
    "kuber"  = "we deployed the service on Kubernetes last night"
})

# --- Control clips ------------------------------------------------------------
# Ordinary business speech containing NO glossary terms, seeded with words that
# sit phonetically close to them. Any correction that fires here is a false
# positive, which is the worst failure this system can have.
Write-Host "David - control clips (no jargon)"
Write-Clips ([ordered]@{
    "c1" = "the number of trades settled quarterly was higher than the estimate"
    "c2" = "please review the quarterly report before the meeting on Monday"
    "c3" = "the auditor asked for a breakdown of the reconciliation batch"
    "c4" = "we should park that item and come back to it next week"
})

# --- Speaker two --------------------------------------------------------------
# A second voice, so results are not tied to one set of acoustics.
Write-Host "Zira - jargon clips"
$synth.SelectVoice("Microsoft Zira Desktop")
Write-Clips ([ordered]@{
    "z1" = "the Quantex pipeline feeds Halberd every morning"
    "z2" = "C R I M S flagged three exceptions in the Nimbus tier"
    "z3" = "Orbex reconciliation runs before the C R I M S batch"
})

$synth.SetOutputToNull()
$synth.Dispose()
Write-Host "`nDone. Re-measure with: python eval/run_eval.py"
