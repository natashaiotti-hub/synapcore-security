#!/usr/bin/env bash
set -euo pipefail

export DO_NOT_TRACK=1
export SYNAPCORE_TELEMETRY=0

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

REGISTRY_FILE="synapcore_state_registry.json"
SHIELD_SCRIPT="synapcore_shield.py"

printf "%b============================================================%b\n" "$CYAN" "$NC"
printf "%b   SYNAPCORE STATE SHIELD - TERMINAL HUD v4.0 (VANGUARD)    %b\n" "$CYAN" "$NC"
printf "%b============================================================%b\n" "$CYAN" "$NC"

unlock_kernel_immutable() {
    if [ -f "$REGISTRY_FILE" ] && command -v chattr >/dev/null 2>&1; then
        if [ "$(id -u)" -eq 0 ]; then
            chattr -i "$REGISTRY_FILE" 2>/dev/null || true
        fi
    fi
}

lock_kernel_immutable() {
    if [ -f "$REGISTRY_FILE" ] && command -v chattr >/dev/null 2>&1; then
        if [ "$(id -u)" -eq 0 ]; then
            chattr +i "$REGISTRY_FILE" 2>/dev/null && \
                printf "%b[KERNEL LOCK] Atributo imutavel (chattr +i) aplicado em %s.%b\n" "$GREEN" "$REGISTRY_FILE" "$NC" || true
        else
            printf "%b[AVISO] Execute com sudo se desejar aplicar trava de kernel (chattr +i) no JSON.%b\n" "$YELLOW" "$NC"
        fi
    fi
}

MODE="${1:---help}"

case "$MODE" in
    --init)
        shift || true
        printf "\n[*] Preparando selagem criptografica PBKDF2-HMAC-SHA256 e Cofre Auto-Heal...\n"
        unlock_kernel_immutable
        if python3 "$SHIELD_SCRIPT" --init "$@"; then
            lock_kernel_immutable
            printf "%b[OK] Sistema selado e verificado com sucesso.%b\n" "$GREEN" "$NC"
        else
            printf "%b[ERRO] Falha durante a inicializacao da Matriz de Estados.%b\n" "$RED" "$NC"
            exit 1
        fi
        ;;
    --check)
        shift || true
        printf "\n[*] Executando auditoria profunda (IMA/EVM, PCR, /proc, Rede e Shell)...\n"
        if python3 "$SHIELD_SCRIPT" --check "$@"; then
            printf "%b[OK] Integridade confirmada pelo lancador.%b\n" "$GREEN" "$NC"
        else
            printf "%b[ALERTA] Violacao detectada. Verifique o relatorio acima.%b\n" "$RED" "$NC"
            exit 1
        fi
        ;;
    --heal)
        shift || true
        printf "\n[*] Executando verificacao com Auto-Healing ativo (Restauracao de Cofre)...\n"
        unlock_kernel_immutable
        python3 "$SHIELD_SCRIPT" --check --heal "$@"
        lock_kernel_immutable
        ;;
    --daemon)
        shift || true
        printf "\n[*] Iniciando Watchdog em Tempo Real (Circuit Breaker + Heartbeat)...\n"
        python3 "$SHIELD_SCRIPT" --daemon "$@"
        ;;
    *)
        printf "\nModos de Operacao (v4.0):\n"
        printf "  %b./synapcore_run.sh --init%b           -> Gera o baseline PBKDF2-HMAC, cria o Cofre e aplica trava chattr.\n" "$CYAN" "$NC"
        printf "  %b./synapcore_run.sh --check%b          -> Audita arquivos (IMA/EVM), ambiente, rede (/proc/net/tcp) e processos.\n" "$CYAN" "$NC"
        printf "  %b./synapcore_run.sh --heal%b           -> Audita e restaura automaticamente arquivos adulterados via Cofre.\n" "$CYAN" "$NC"
        printf "  %b./synapcore_run.sh --daemon [--heal]%b -> Monitora a maquina continuamente em tempo real.\n" "$CYAN" "$NC"
        ;;
esac
