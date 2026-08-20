# Regenerate the evaluation corpus with Windows speech synthesis.
#   powershell -ExecutionPolicy Bypass -File scripts/make_test_audio.ps1
#
# Synthetic speech is a weaker test than human speech. Replace these clips with
# real recordings before trusting the numbers for a production decision.
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
    16000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono)
$dir = Join-Path $PSScriptRoot "..\eval\audio"
New-Item -ItemType Directory -Force $dir | Out-Null
$synth.Rate = -1

$clips = [ordered]@{
  "j1"     = "the Quantex pipeline feeds Halberd every morning"
  "j2"     = "C R I M S flagged three exceptions in the Nimbus tier"
  "j3"     = "we migrated Vectrabridge onto the Skylark platform"
  "j4"     = "Orbex reconciliation runs before the C R I M S batch"
  "arr"    = "our A R R grew twelve percent this quarter"
  "ebitda" = "the E B I T D A margin improved significantly"
  "kuber"  = "we deployed the service on Kubernetes last night"
}

foreach ($name in $clips.Keys) {
  $path = Join-Path $dir "$name.wav"
  $synth.SetOutputToWaveFile($path, $format)
  $synth.Speak($clips[$name])
  Write-Host "wrote $name.wav"
}
$synth.SetOutputToNull()
$synth.Dispose()
