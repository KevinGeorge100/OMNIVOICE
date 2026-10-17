param(
    [Parameter(Mandatory = $true)][string]$TextPath,
    [Parameter(Mandatory = $true)][string]$WavePath
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$format = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(
    8000,
    [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
    [System.Speech.AudioFormat.AudioChannel]::Mono
)
$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $synth.SetOutputToWaveFile($WavePath, $format)
    $synth.Speak([System.IO.File]::ReadAllText($TextPath))
} finally {
    $synth.Dispose()
}
