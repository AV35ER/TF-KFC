param(
    [string]$JflapJar = $env:JFLAP_JAR,
    [string]$JflapVersion = '7.1 (JFLAP7.1.jar; manifest has no Implementation-Version)'
)

$ErrorActionPreference = 'Continue'
$evidenceDir = $PSScriptRoot
$projectRoot = (Resolve-Path (Join-Path $evidenceDir '..\..\..')).Path
$sourceWorkspaceJar = Join-Path (Split-Path $projectRoot -Parent) 'analizador-kfc-main\.tools\jflap\JFLAP7.1.jar'
if ([string]::IsNullOrWhiteSpace($JflapJar)) {
    if (Test-Path -LiteralPath $sourceWorkspaceJar) { $JflapJar = $sourceWorkspaceJar }
    else { throw 'Indica el JAR original con -JflapJar o define JFLAP_JAR.' }
}
$JflapJar = (Resolve-Path -LiteralPath $JflapJar).Path
$java = (Get-Command java -ErrorAction Stop).Source
$javac = (Get-Command javac -ErrorAction Stop).Source
$source = Join-Path $evidenceDir 'JflapMotorCheck.java'
$report = Join-Path $evidenceDir 'reporte-jflap.json'
$table = Join-Path $evidenceDir 'resultados-jflap.md'
$log = Join-Path $evidenceDir 'ejecucion-completa.log'
$api = Join-Path $evidenceDir 'inspeccion-api-jflap.txt'
$logLines = [System.Collections.Generic.List[string]]::new()
$apiLines = [System.Collections.Generic.List[string]]::new()
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$tempClasses = [IO.Path]::GetFullPath((Join-Path $tempRoot ('jflap-motor-' + [guid]::NewGuid().ToString('N'))))
if (-not $tempClasses.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Compiled classes path is outside the expected temporary directory.'
}
New-Item -ItemType Directory -Path $tempClasses | Out-Null

try {
    [void]$logLines.Add("JFLAP MOTOR TEST - $(Get-Date -Format o)")
    [void]$logLines.Add("JAR: $(Split-Path $JflapJar -Leaf)")
    [void]$logLines.Add("JFLAP_VERSION: $JflapVersion")
    [void]$logLines.Add("JAR_SHA256: $((Get-FileHash -LiteralPath $JflapJar -Algorithm SHA256).Hash)")
    [void]$logLines.Add('JAVA_VERSION:')
    & $java -version 2>&1 | ForEach-Object { $line = [string]$_; Write-Host $line; [void]$logLines.Add($line) }
    [void]$logLines.Add('JAVAC_VERSION:')
    & $javac -version 2>&1 | ForEach-Object { $line = [string]$_; Write-Host $line; [void]$logLines.Add($line) }

    [void]$apiLines.Add('API_SIGNATURES (javap):')
    & javap -classpath $JflapJar -public file.XMLCodec file.xml.TransducerFactory file.xml.FSATransducer file.xml.AutomatonTransducer automata.fsa.FiniteStateAutomaton automata.AutomatonSimulator automata.SimulatorFactory automata.fsa.FSAStepWithClosureSimulator 2>&1 |
        ForEach-Object { $line = [string]$_; Write-Host $line; [void]$apiLines.Add($line); [void]$logLines.Add($line) }
    if ($LASTEXITCODE -ne 0) { throw 'javap could not inspect the actual JAR classes.' }
    [void]$logLines.Add('JAVAP_EXIT_CODE: 0')

    [void]$logLines.Add('COMPILATION:')
    & $javac -encoding UTF-8 -classpath $JflapJar -d $tempClasses $source 2>&1 |
        ForEach-Object { $line = [string]$_; Write-Host $line; [void]$logLines.Add($line) }
    if ($LASTEXITCODE -ne 0) { throw 'javac could not compile the temporary runner.' }
    [void]$logLines.Add('COMPILATION_EXIT_CODE: 0')

    [void]$logLines.Add('SIMULATIONS (java.awt.headless=true):')
    $jarHash = (Get-FileHash -LiteralPath $JflapJar -Algorithm SHA256).Hash
    & $java '-Djava.awt.headless=true' -classpath "$tempClasses;$JflapJar" JflapMotorCheck `
        $projectRoot $JflapVersion $jarHash $report $table 2>&1 |
        ForEach-Object { $line = [string]$_; Write-Host $line; [void]$logLines.Add($line) }
    $exitCode = $LASTEXITCODE
    [void]$logLines.Add("JAVA_EXIT_CODE: $exitCode")
    if ($exitCode -ne 0) { throw "JFLAP runner exited with code $exitCode; review $log and $report." }
    [void]$logLines.Add('REPORT: reporte-jflap.json')
    [void]$logLines.Add('TABLE: resultados-jflap.md')
    Write-Host "Reporte: $report"
    Write-Host "Tabla:   $table"
    Write-Host "Log:     $log"
}
finally {
    $logLines | Set-Content -LiteralPath $log -Encoding utf8
    $apiLines | Set-Content -LiteralPath $api -Encoding utf8
    if ((Test-Path -LiteralPath $tempClasses) -and
        $tempClasses.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $tempClasses -Leaf) -match '^jflap-motor-[0-9a-f]{32}$') {
        Remove-Item -LiteralPath $tempClasses -Recurse -Force
    }
}
