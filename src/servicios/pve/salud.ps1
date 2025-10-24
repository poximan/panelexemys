<# 
  Script: Listar info de VMs específicas por VMID (parámetro obligatorio -vhost)
  Uso:
    .\listar-vms.ps1 -vhost 101,102
#>

param(
  [Parameter(Mandatory = $true)]
  [int[]] $vhost  # VMIDs a consultar (ej: 101,102,1104)
)

# ==========================
# Desactivar validación SSL (laboratorio) - idempotente
# ==========================
if (-not ("TrustAllCertsPolicy" -as [type])) {
    add-type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCertsPolicy : ICertificatePolicy {
    public bool CheckValidationResult(
        ServicePoint srvPoint, X509Certificate certificate,
        WebRequest request, int certificateProblem) { return true; }
}
"@
}
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy

# ==========================
# Configuración API (mismo hypervisor)
# ==========================
$BaseUrl = "https://10.10.9.245:8006/api2/json"
$Headers = @{ Authorization = "PVEAPIToken=root@pam!apinguear=ca4211e8-e20c-4158-94a6-ed7509eea094" }
$Node    = "pve-comu"

# ==========================
# Traer todas las VMs QEMU del nodo
# ==========================
$qemu = Invoke-RestMethod -Uri "$BaseUrl/nodes/$Node/qemu" -Headers $Headers -ErrorAction Stop

if (-not $qemu.data) {
    Write-Warning "No se recibieron VMs de /qemu en el nodo '$Node'."
    return
}

# ==========================
# Filtrar por los VMIDs solicitados (-vhost)
# ==========================
$filtered = $qemu.data | Where-Object { $vhost -contains $_.vmid }

# Avisar por los VMID no encontrados en la respuesta
$missing = $vhost | Where-Object { $_ -notin ($qemu.data.vmid) }
if ($missing) {
    Write-Warning ("VMIDs no presentes en el nodo {0}: {1}" -f $Node, ($missing -join ", "))
}

if (-not $filtered) {
    Write-Warning "No hay coincidencias para los VMIDs solicitados."
    return
}

# ==========================
# Mostrar en tabla con métricas legibles
# ==========================
$filtered | ForEach-Object {
    [PSCustomObject]@{
        VMID    = $_.vmid
        Name    = $_.name
        Status  = $_.status
        CPUs    = $_.cpus
        CPUuse  = ("{0:P2}" -f ($_.cpu))
        MemUse  = ("{0:N1} GB" -f ($_.mem / 1GB))
        MemMax  = ("{0:N1} GB" -f ($_.maxmem / 1GB))
        Uptime  = ("{0:dd}d {0:hh}h {0:mm}m" -f ([TimeSpan]::FromSeconds([double]($_.uptime))))
    }
} | Sort-Object VMID | Format-Table -AutoSize