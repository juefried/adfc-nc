$scriptblock = {
    param($wordToComplete, $commandAst, $cursorPosition)

    $previous = @{
        _ADFC_NC_COMPLETE = $Env:_ADFC_NC_COMPLETE
        _TYPER_COMPLETE_ARGS = $Env:_TYPER_COMPLETE_ARGS
        _TYPER_COMPLETE_WORD_TO_COMPLETE = $Env:_TYPER_COMPLETE_WORD_TO_COMPLETE
    }

    $Env:_ADFC_NC_COMPLETE = "complete_powershell"
    $Env:_TYPER_COMPLETE_ARGS = $commandAst.ToString()
    $Env:_TYPER_COMPLETE_WORD_TO_COMPLETE = $wordToComplete

    try {
        adfc-nc | ForEach-Object {
            $commandArray = $_ -Split ":::", 2
            if ($commandArray.Count -ge 2) {
                $command = $commandArray[0]
                $helpString = $commandArray[1]
                [System.Management.Automation.CompletionResult]::new(
                    $command, $command, 'ParameterValue', $helpString)
            }
        }
    }
    finally {
        foreach ($name in $previous.Keys) {
            if ($null -eq $previous[$name]) {
                Remove-Item "Env:$name" -ErrorAction SilentlyContinue
            }
            else {
                Set-Item "Env:$name" $previous[$name]
            }
        }
    }
}
Register-ArgumentCompleter -Native -CommandName adfc-nc -ScriptBlock $scriptblock
