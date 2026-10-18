# Envia o radar/vagas para o servidor caseiro (Termux no celular via Tailscale) e reinicia.
# Uso: powershell -File deploy.ps1
$ErrorActionPreference = "Stop"
$HostIp = "100.98.189.36"
$Port = 8022
$Remote = "radar-vagas"
Set-Location $PSScriptRoot

$files = @("app.py", "radar", "requirements.txt", "servidor.sh", "README.md")
tar -czf "$env:TEMP\radar.tgz" --exclude=__pycache__ @files
scp -P $Port "$env:TEMP\radar.tgz" "${HostIp}:radar.tgz"
$boot = "~/.termux/boot/iniciar-servidores.sh"  # liga sozinho quando o celular reinicia
ssh -p $Port $HostIp "mkdir -p ~/$Remote && tar -xzf ~/radar.tgz -C ~/$Remote && rm ~/radar.tgz && sed -i 's/\r$//' ~/$Remote/servidor.sh && (grep -q radar-vagas $boot || echo 'sh ~/radar-vagas/servidor.sh iniciar' >> $boot) && sh ~/$Remote/servidor.sh reiniciar"
Write-Host "Pronto: http://${HostIp}:5070"
