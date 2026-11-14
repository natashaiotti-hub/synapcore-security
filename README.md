# SYNAPCORE SECURITY FRAMEWORK (v4.0)
> Arquitetura Autonoma de Integridade Criptografica, Cyber Deception e Resposta Tatil Out-of-Band (BLE)

O **Synapcore** e um ecossistema modular de defesa ativa de endpoints Linux desenvolvido para operar com **zero telemetria externa**, deteccao de intrusao em tempo real, auto-recuperacao de arquivos (*auto-healing*) e alerta tatil imediato no pulso do operador via Bluetooth Low Energy (BLE).

## Arquitetura Integrada (4 Camadas)
1. **Sensor de Rede (`02-active-deception/`):** Ratoeira TCP (porta 3333) via `socat` com captura de IP/porta e resposta visual estroboscopica.
2. **Cerebro de Estado (`01-state-shield-v4/`):** Auditoria em Python puro com `PBKDF2-HMAC-SHA256` (600.000 iteracoes), cadeia cumulativa estilo TPM (PCR), leitura nativa de `/proc` e Cofre Auto-Heal.
3. **Telemetria Auditiva (`04-earth-dsp-telemetry/`):** Sintese FM e acustica calibrada em 48 kHz ancorada em Re (`36.71 Hz`) com headroom em `-6.0 dBFS`.
4. **Resposta Out-of-Band (`03-companion-ble-pager/`):** Ponte ADB que aciona um app Android nativo (Kotlin) com negociacao de MTU 247 e calculo de checksum **CRC-16 Modbus (`0xA001`)** para vibrar o smartwatch do analista em tempo real.

## Inicio Rapido (State Shield v4.0)
    cd 01-state-shield-v4
    chmod +x synapcore_shield.py synapcore_run.sh
    ./synapcore_run.sh --init --targets synapcore_shield.py synapcore_run.sh
    ./synapcore_run.sh --daemon --heal --interval 5
