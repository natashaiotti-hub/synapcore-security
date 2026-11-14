#!/usr/bin/env python3
"""
Synapcore State Shield & Cryptographic Integrity Verifier v4.0
Arquitetura de Defesa Ativa, Zero Telemetria e Resiliencia Autonoma.
"""

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import math
import os
import shutil
import stat
import struct
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone

os.environ["DO_NOT_TRACK"] = "1"
os.environ["SYNAPCORE_TELEMETRY"] = "0"

STATE_REGISTRY_FILE = "synapcore_state_registry.json"
VAULT_DIR = ".synapcore_vault"
PBKDF2_ITERATIONS = 600_000
CRITICAL_ENV_VARS = ["PATH", "USER", "SHELL", "HOME", "LD_PRELOAD", "LD_LIBRARY_PATH", "SYNAPCORE_MODE"]

SUSPICIOUS_PATTERNS = [
    "rm -rf /",
    ":(){ :|:& };:",
    "nc -e",
    "ncat -e",
    "mkfifo",
    "base64 -d",
    "/dev/tcp/",
    "/dev/udp/",
    "bash -i",
    "sh -i",
    "socat exec:",
    "unset histfile",
    "histfile=/dev/null",
    "chattr -i",
    "LD_PRELOAD=",
]


class SynapcoreShieldV4:
    def __init__(self, registry_path: str = STATE_REGISTRY_FILE, vault_dir: str = VAULT_DIR):
        self.registry_path = registry_path
        self.vault_dir = vault_dir
        self.today_key = datetime.now(timezone.utc).strftime("%Y%m%d")

    def _get_operator_pin(self, prompt_text: str = "PIN Numerico Secreto Synapcore: ") -> str:
        env_pin = os.getenv("SYNAPCORE_PIN")
        if env_pin:
            return env_pin.strip()
        try:
            return (os.environ.get("SYNAPCORE_PIN") or getpass.getpass(prompt_text)).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[ABORTADO] Entrada de PIN cancelada pelo operador.")
            sys.exit(1)

    def _derive_master_key(self, pin: str, salt_bytes: bytes) -> bytes:
        combined_secret = f"{pin}:{self.today_key}".encode("utf-8")
        return hashlib.pbkdf2_hmac(
            "sha256",
            combined_secret,
            salt_bytes,
            PBKDF2_ITERATIONS,
            dklen=32,
        )

    @staticmethod
    def _canonical_json_bytes(payload_dict: dict) -> bytes:
        return json.dumps(payload_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _compute_hmac_seal(self, master_key: bytes, payload_dict: dict) -> str:
        msg = self._canonical_json_bytes(payload_dict)
        return hmac.new(master_key, msg, hashlib.sha256).hexdigest()

    @staticmethod
    def _pcr_extend(current_pcr: str, measurement_str: str) -> str:
        m_hash = hashlib.sha256(measurement_str.encode("utf-8")).hexdigest()
        combined = f"{current_pcr}{m_hash}".encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def _measure_file_ima_evm(self, filepath: str) -> dict | None:
        sha256_hash = hashlib.sha256()
        try:
            st = os.stat(filepath, follow_symlinks=False)
            if not stat.S_ISREG(st.st_mode):
                return None
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(byte_block)
            content_hash = sha256_hash.hexdigest()
            mode_octal = oct(stat.S_IMODE(st.st_mode))
            evm_string = f"{content_hash}:{mode_octal}:{st.st_uid}:{st.st_gid}:{st.st_size}"
            evm_digest = hashlib.sha256(evm_string.encode("utf-8")).hexdigest()
            return {
                "sha256": content_hash,
                "mode": mode_octal,
                "uid": st.st_uid,
                "gid": st.st_gid,
                "size": st.st_size,
                "evm_digest": evm_digest,
            }
        except (FileNotFoundError, PermissionError):
            return None

    def _backup_to_vault(self, filepath: str, file_sha256: str) -> bool:
        try:
            os.makedirs(self.vault_dir, mode=0o700, exist_ok=True)
            vault_target = os.path.join(self.vault_dir, f"{file_sha256}.bak")
            shutil.copy2(filepath, vault_target)
            os.chmod(vault_target, 0o400)
            return True
        except Exception:
            return False

    def _heal_file_from_vault(self, filepath: str, expected_meta: dict) -> bool:
        vault_source = os.path.join(self.vault_dir, f"{expected_meta['sha256']}.bak")
        if not os.path.exists(vault_source):
            return False
        try:
            vault_check = self._measure_file_ima_evm(vault_source)
            if not vault_check or vault_check["sha256"] != expected_meta["sha256"]:
                print(f"[ERRO DE COFRE] Backup de {filepath} corrompido. Abortando restauracao.")
                return False
            shutil.copy2(vault_source, filepath)
            os.chmod(filepath, int(expected_meta["mode"], 8))
            print(f"[AUTO-HEAL] Arquivo restaurado com sucesso ao estado integro: {filepath}")
            return True
        except Exception as e:
            print(f"[FALHA AUTO-HEAL] Nao foi possivel restaurar {filepath}: {e}")
            return False

    def _get_env_snapshot(self) -> dict:
        snapshot = {}
        for var in CRITICAL_ENV_VARS:
            val = os.getenv(var, "<UNSET>")
            snapshot[var] = hashlib.sha256(f"{var}={val}".encode("utf-8")).hexdigest()
        return snapshot

    def _audit_shell_histories(self) -> tuple[bool, list[str]]:
        history_files = [
            os.path.expanduser("~/.zsh_history"),
            os.path.expanduser("~/.bash_history"),
        ]
        alerts = []
        inspected_any = False

        for hpath in history_files:
            if not os.path.exists(hpath):
                continue
            inspected_any = True
            try:
                with open(hpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-40:]
                for raw_line in lines:
                    clean_line = raw_line.split(";", 1)[-1].strip() if raw_line.startswith(":") and ";" in raw_line else raw_line.strip()
                    lower_line = clean_line.lower()
                    for pattern in SUSPICIOUS_PATTERNS:
                        if pattern.lower() in lower_line:
                            alerts.append(f"Historico ({os.path.basename(hpath)}): '{clean_line}'")
            except Exception as e:
                alerts.append(f"Erro ao auditar {hpath}: {e}")

        if alerts:
            return False, alerts
        msg = "Historicos ZSH/Bash auditados e limpos." if inspected_any else "Nenhum arquivo de historico ZSH/Bash ativo."
        return True, [msg]

    def _audit_live_procfs(self) -> tuple[bool, list[str]]:
        if not os.path.exists("/proc"):
            return True, ["Sistema /proc indisponivel neste ambiente."]

        alerts = []
        my_pid = os.getpid()

        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if pid == my_pid:
                continue
            cmdline_path = f"/proc/{pid}/cmdline"
            try:
                with open(cmdline_path, "rb") as f:
                    raw = f.read(4096)
                if not raw:
                    continue
                cmd_str = raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
                lower_cmd = cmd_str.lower()
                for pattern in SUSPICIOUS_PATTERNS:
                    if pattern.lower() in lower_cmd:
                        alerts.append(f"Processo Suspeito em Memoria [PID {pid}]: {cmd_str}")
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue

        if alerts:
            return False, alerts
        return True, ["Memoria de processos (/proc) limpa de assinaturas de intrusao."]

    @staticmethod
    def _get_listening_ports_procfs() -> list[int]:
        listening_ports = set()
        for net_file in ("/proc/net/tcp", "/proc/net/tcp6"):
            if not os.path.exists(net_file):
                continue
            try:
                with open(net_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()[1:]
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) < 4:
                        continue
                    local_address, state = parts[1], parts[3]
                    if state == "0A":
                        port_hex = local_address.split(":")[-1]
                        listening_ports.add(int(port_hex, 16))
            except Exception:
                continue
        return sorted(listening_ports)

    def _trigger_alarm(self):
        import getpass, sys
        wav = "/var/tmp/synapcore-schranz.wav"
        print("
" + "="*60)
        print(" [!] ALERTA CRITICO: VIOLACAO DE INTEGRIDADE DETECTADA!")
        print(" [!] O alarme continuara tocando em loop ate que o PIN correto seja fornecido.")
        print("="*60 + "
")
        while True:
            # Disparo duplo assincrono (Audio PipeWire + Smartwatch BLE)
            cmd_audio = f"sudo -u synapcore XDG_RUNTIME_DIR=/run/user/$(id -u synapcore 2>/dev/null || echo 1000) play -q {wav} 2>/dev/null || aplay -q {wav} 2>/dev/null || true"
            cmd_ble = "sudo -u synapcore timeout 4 adb shell am broadcast -a com.synapcore.ALERTA_INVASAO -p com.synapcore.companion --es titulo ALARME_TRAVADO --es mensagem PIN_OBRIGATORIO >/dev/null 2>&1 || true"
            os.system(f"({cmd_audio}) & ({cmd_ble}) &")
            
            try:
                # Exige a senha para desarmar
                pin_input = getpass.getpass("Digite o PIN para DESARMAR o alarme: ")
                if hmac.compare_digest(hashlib.sha256(pin_input.encode()).hexdigest(), self.config.get("pin_hash", "")):
                    print("[OK] PIN correto. Alarme desarmado e sistema estabilizado.")
                    break
                else:
                    print("[ERRO] PIN incorreto! O alarme persiste.")
            except (KeyboardInterrupt, EOFError):
                print("
[AVISO] Interrupcao ignorada. O sistema exige o PIN de desarmamento.")

    def initialize_registry(self, monitored_files: list[str], active_mode_code: str = "170") -> bool:
        pin = self._get_operator_pin("Digite o PIN Numerico Secreto para SELAR a Matriz (--init): ")
        if not pin:
            print("[ERRO] O PIN numerico nao pode ser vazio.")
            return False

        salt_bytes = os.urandom(16)
        master_key = self._derive_master_key(pin, salt_bytes)

        pcr_value = "0" * 64
        files_record = {}

        print(f"\n--- Inicializando Registro Oficial Synapcore v4.0 (Modo {active_mode_code}) ---")
        for filepath in sorted(set(monitored_files)):
            meta = self._measure_file_ima_evm(filepath)
            if meta:
                files_record[filepath] = meta
                pcr_value = self._pcr_extend(pcr_value, f"FILE:{filepath}:{meta['evm_digest']}")
                backed_up = self._backup_to_vault(filepath, meta["sha256"])
                vault_tag = "[Cofre OK]" if backed_up else "[Sem Cofre]"
                print(
                    f"[+] Protegido: {filepath} | SHA256: {meta['sha256'][:12]}... "
                    f"| Mode: {meta['mode']} {vault_tag}"
                )
            else:
                print(f"[-] Aviso: Alvo '{filepath}' nao encontrado ou inacessivel.")

        env_snapshot = self._get_env_snapshot()
        for k, v in sorted(env_snapshot.items()):
            pcr_value = self._pcr_extend(pcr_value, f"ENV:{k}:{v}")

        listening_ports = self._get_listening_ports_procfs()
        pcr_value = self._pcr_extend(pcr_value, f"PORTS:{','.join(map(str, listening_ports))}")

        payload = {
            "version": "4.0.0",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "daily_key": self.today_key,
            "active_mode": active_mode_code,
            "kdf": {
                "algorithm": "PBKDF2-HMAC-SHA256",
                "iterations": PBKDF2_ITERATIONS,
                "salt_b64": base64.b64encode(salt_bytes).decode("ascii"),
            },
            "files": files_record,
            "env_baseline": env_snapshot,
            "listening_ports_baseline": listening_ports,
            "pcr_aggregate": pcr_value,
        }

        hmac_signature = self._compute_hmac_seal(master_key, payload)
        full_registry = {
            "payload": payload,
            "hmac_sha256": hmac_signature,
        }

        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(full_registry, f, indent=4, sort_keys=True)
        os.chmod(self.registry_path, 0o600)

        print("\n[OK] Matriz de Estados v4.0 selada com sucesso.")
        print(f"  -> PCR Aggregate : {pcr_value[:24]}...")
        print(f"  -> Selo HMAC     : {hmac_signature[:24]}...")
        print(f"  -> Portas Base   : {listening_ports if listening_ports else 'Nenhuma porta TCP aberta'}")
        return True

    def verify_integrity(self, pin_override: str | None = None, auto_heal: bool = False) -> bool:
        if not os.path.exists(self.registry_path):
            print("[ERRO CRITICO] Registro oficial nao encontrado. Execute primeiro com --init.")
            self._trigger_alarm()
            return False

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                full_registry = json.load(f)
            payload = full_registry["payload"]
            stored_hmac = full_registry["hmac_sha256"]
            salt_bytes = base64.b64decode(payload["kdf"]["salt_b64"])
        except Exception as e:
            print(f"[VIOLACAO ESTRUTURAL] Arquivo de registro corrompido ou adulterado: {e}")
            self._trigger_alarm()
            return False

        pin = pin_override if pin_override is not None else self._get_operator_pin("Digite o PIN Numerico Secreto para VALIDAR o Estado: ")

        if payload.get("daily_key") != self.today_key:
            print(
                f"[ALERTA TEMPORAL] Chave diaria expirada ou divergente. "
                f"Esperada: {self.today_key} | Registro: {payload.get('daily_key')}"
            )
            self._trigger_alarm()
            return False

        master_key = self._derive_master_key(pin, salt_bytes)
        computed_hmac = self._compute_hmac_seal(master_key, payload)
        if not hmac.compare_digest(stored_hmac, computed_hmac):
            print("\n[VIOLACAO CRIPTOGRAFICA] Selo HMAC-SHA256 INVALIDO.")
            print("  -> Causa: PIN incorreto ou tentativa de adulteracao direta do arquivo JSON.")
            self._trigger_alarm()
            return False

        print(f"\n--- Auditoria Synapcore Shield v4.0 (Modo {payload.get('active_mode')} | HMAC Verificado) ---")
        breach_detected = False
        recomputed_pcr = "0" * 64

        for filepath, expected_meta in sorted(payload["files"].items()):
            current_meta = self._measure_file_ima_evm(filepath)
            if current_meta is None:
                print(f"[VIOLACAO DE ARQUIVO] Arquivo critico removido ou inacessivel: {filepath}")
                breach_detected = True
                if auto_heal:
                    self._heal_file_from_vault(filepath, expected_meta)
            elif current_meta["evm_digest"] != expected_meta["evm_digest"]:
                print(f"[VIOLACAO IMA/EVM] Adulteracao detectada em: {filepath}")
                if current_meta["sha256"] != expected_meta["sha256"]:
                    print(f"  -> Hash esperado : {expected_meta['sha256'][:16]}...")
                    print(f"  -> Hash atual    : {current_meta['sha256'][:16]}...")
                if current_meta["mode"] != expected_meta["mode"] or current_meta["uid"] != expected_meta["uid"]:
                    print(
                        f"  -> Metadados esperados (Mode/UID): {expected_meta['mode']}/{expected_meta['uid']} "
                        f"| Atuais: {current_meta['mode']}/{current_meta['uid']}"
                    )
                breach_detected = True
                if auto_heal:
                    self._heal_file_from_vault(filepath, expected_meta)
            else:
                print(f"[Integro IMA/EVM] {filepath} (Mode {current_meta['mode']})")
                recomputed_pcr = self._pcr_extend(recomputed_pcr, f"FILE:{filepath}:{current_meta['evm_digest']}")

        current_env = self._get_env_snapshot()
        for var, expected_hash in sorted(payload.get("env_baseline", {}).items()):
            curr_hash = current_env.get(var)
            if curr_hash != expected_hash:
                print(f"[VIOLACAO DE AMBIENTE] Desvio detectado na variavel critica: {var}")
                breach_detected = True
            else:
                recomputed_pcr = self._pcr_extend(recomputed_pcr, f"ENV:{var}:{curr_hash}")

        current_ports = self._get_listening_ports_procfs()
        expected_ports = payload.get("listening_ports_baseline", [])
        recomputed_pcr = self._pcr_extend(recomputed_pcr, f"PORTS:{','.join(map(str, current_ports))}")
        unexpected_ports = set(current_ports) - set(expected_ports)
        if unexpected_ports:
            print(f"[VIOLACAO DE REDE] Novas portas TCP abertas fora do baseline: {sorted(unexpected_ports)}")
            breach_detected = True
        else:
            print(f"[Integro Rede] Portas TCP em escuta identicas ao baseline: {current_ports}")

        if not breach_detected and recomputed_pcr != payload.get("pcr_aggregate"):
            print("[VIOLACAO PCR] Divergencia na cadeia cumulativa de estado (PCR Aggregate).")
            breach_detected = True

        hist_ok, hist_msgs = self._audit_shell_histories()
        for m in hist_msgs:
            print(f"[Auditoria Shell] {m}")
        if not hist_ok:
            breach_detected = True

        proc_ok, proc_msgs = self._audit_live_procfs()
        for m in proc_msgs:
            print(f"[Auditoria /proc] {m}")
        if not proc_ok:
            breach_detected = True

        if breach_detected:
            print("\n[CIRCUIT BREAKER ATIVADO] Violacao de integridade confirmada. Disparando alarme...")
            self._trigger_alarm()
            return False

        print(f"\n[STATUS: 100% - SINCRONIZADO] PCR Validado ({recomputed_pcr[:16]}...). Ponto maximo preservado.")
        return True

    def run_watchdog_daemon(self, interval_sec: int = 5, auto_heal: bool = True):
        pin = self._get_operator_pin("Digite o PIN Numerico Secreto para iniciar o Daemon Watchdog: ")
        seq = 0
        print(f"\n[*] Watchdog Synapcore v4.0 ativo (Intervalo: {interval_sec}s | Auto-Heal: {auto_heal})")
        try:
            while True:
                seq += 1
                ok = self.verify_integrity(pin_override=pin, auto_heal=auto_heal)
                hb_token = hashlib.sha256(f"{seq}:{self.today_key}:{ok}".encode("utf-8")).hexdigest()[:12]
                print(f"[HEARTBEAT #{seq:04d}] Token={hb_token} | Status={'OK' if ok else 'BREACH'}")
                if not ok and not auto_heal:
                    print("[LOCKDOWN] Encerrando execucao por violacao critica sem Auto-Heal.")
                    sys.exit(1)
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            print("\n[*] Daemon Watchdog encerrado pelo operador.")


def main():
    parser = argparse.ArgumentParser(
        description="Synapcore State Shield v4.0 - Verificador de Integridade Criptografica e Defesa Ativa"
    )
    parser.add_argument("--init", action="store_true", help="Inicializa e sela o Registro Oficial de Estado com PIN e HMAC")
    parser.add_argument("--check", action="store_true", help="Verifica a integridade de arquivos, ambiente, rede e processos")
    parser.add_argument("--heal", action="store_true", help="Restaura automaticamente arquivos modificados a partir do Cofre")
    parser.add_argument("--daemon", action="store_true", help="Executa em loop continuo (Watchdog em tempo real)")
    parser.add_argument("--interval", type=int, default=5, help="Intervalo em segundos para o modo --daemon (padrao: 5)")
    parser.add_argument("--mode", type=str, default="170", help="Codigo do modo operacional ativo (padrao: 170)")
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["synapcore_shield.py", "synapcore_run.sh"],
        help="Lista de arquivos criticos para proteger",
    )

    args = parser.parse_args()
    shield = SynapcoreShieldV4()

    if args.init:
        ok = shield.initialize_registry(args.targets, active_mode_code=args.mode)
        sys.exit(0 if ok else 1)
    elif args.daemon:
        shield.run_watchdog_daemon(interval_sec=args.interval, auto_heal=args.heal)
    else:
        ok = shield.verify_integrity(auto_heal=args.heal)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
