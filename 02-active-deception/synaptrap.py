#!/usr/bin/env python3
import asyncio
import logging
import secrets
import sys
import time
from collections import defaultdict, deque

logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")

HOST = "0.0.0.0"
PORT = 2222
MAX_CONCURRENT = 40
TARPIT_CYCLES = 20
TARPIT_DELAY = 3.5
DECOY_BANNER = b"SSH-2.0-OpenSSH_9.2p1 Debian-2+deb12u3\r\n"

ip_history = defaultdict(lambda: deque(maxlen=10))
active_slots = asyncio.Semaphore(MAX_CONCURRENT)


def is_burst_bot(ip: str, now: float) -> bool:
    hist = ip_history[ip]
    hist.append(now)
    recent = [t for t in hist if now - t <= 15.0]
    return len(recent) >= 3


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername") or ("unknown", 0)
    ip, port = peer[0], peer[1]

    if active_slots.locked():
        logging.warning(f"[LIMITE_TRAP] Limite de {MAX_CONCURRENT} conexoes atingido; descartando {ip}:{port}")
        writer.close()
        return

    async with active_slots:
        now = time.monotonic()
        burst = is_burst_bot(ip, now)
        logging.warning(f"[ALERTA_TRAP] Intruso interceptado de {ip}:{port}")

        # Observa comportamento inicial (0.6s) para classificar bot vs humano
        initial_data = b""
        elapsed = 0.6
        try:
            t0 = time.monotonic()
            initial_data = await asyncio.wait_for(reader.read(256), timeout=0.6)
            elapsed = time.monotonic() - t0
        except asyncio.TimeoutError:
            pass
        except Exception:
            pass

        is_bot = burst or (bool(initial_data) and elapsed < 0.35)

        try:
            if is_bot:
                sample = initial_data[:60].decode("utf-8", errors="replace").strip()
                logging.warning(
                    f"[PERFIL_ADAPTATIVO] {ip}:{port} -> BOT_SCANNER (burst={burst}, dt={elapsed:.2f}s, payload='{sample}') | Ativando JAULA_TARPIT"
                )
                for step in range(1, TARPIT_CYCLES + 1):
                    # RFC 4253 permite linhas de texto antes do banner SSH-2.0
                    bait = f"X-Synapcore-Sync-{step:02d}: {secrets.token_hex(6)}\r\n".encode("ascii")
                    writer.write(bait)
                    await writer.drain()
                    await asyncio.sleep(TARPIT_DELAY)
            else:
                logging.warning(
                    f"[PERFIL_ADAPTATIVO] {ip}:{port} -> HUMAN_INTERACTIVE (dt={elapsed:.2f}s) | Servindo DECOY_BANNER"
                )
                await asyncio.sleep(1.5)
                writer.write(DECOY_BANNER)
                await writer.drain()
                try:
                    fp = await asyncio.wait_for(reader.read(256), timeout=4.0)
                    if fp:
                        fp_txt = fp[:100].decode("utf-8", errors="replace").strip()
                        logging.warning(f"[FINGERPRINT] {ip}:{port} enviou: '{fp_txt}'")
                except asyncio.TimeoutError:
                    pass
        except (ConnectionResetError, BrokenPipeError):
            logging.info(f"[DESCONEXAO] {ip}:{port} encerrou a conexao durante decepcao.")
        except Exception as exc:
            logging.error(f"[ERRO] {ip}:{port} -> {exc}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    logging.info(f"[SYNAPCORE] Synaptrap v2.0 (Decepcao Adaptativa + Tarpit) ativo na porta {PORT}...")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
