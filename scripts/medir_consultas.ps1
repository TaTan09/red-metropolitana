$psql = @('exec','-i','red_metropolitana_postgres','psql','-U','red_user','-d','red_metropolitana','-t','-A')

foreach ($c in 'A_hechos','B_mart','C_vista') {
    $sql = Get-Content "sql/utilities/consulta_$c.sql" -Raw
    $tiempos = foreach ($i in 1..5) {
        $salida = "explain (analyze) $sql" | docker @psql
        $m = $salida | Select-String 'Execution Time: ([\d.]+) ms'
        [double]$m.Matches[0].Groups[1].Value
    }
    $mediana = ($tiempos | Sort-Object)[2]
    "{0}: primera={1:N1} ms | mediana={2:N1} ms | corridas={3}" -f $c, $tiempos[0], $mediana, (($tiempos | ForEach-Object { '{0:N1}' -f $_ }) -join ', ')
}