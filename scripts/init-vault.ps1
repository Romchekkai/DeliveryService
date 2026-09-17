$env:VAULT_ADDR = "http://127.0.0.1:8200"
$env:VAULT_TOKEN = "dev-root-token"

# ждём, пока Vault поднимется docker start vault-dev .\scripts\init-vault.ps1

for ($i = 0; $i -lt 30; $i++) {
    try {
        $health = Invoke-RestMethod -Uri "$env:VAULT_ADDR/v1/sys/health" -Method Get
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}

docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=dev-root-token vault-dev `
  vault secrets enable transit 2>$null

docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=dev-root-token vault-dev `
  vault write -f transit/keys/user-service-jwt type=rsa-2048 2>$null

Write-Host "Vault transit key ready"