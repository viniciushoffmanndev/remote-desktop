# O programa que irá abrir para controlar o outro PC

import socket
import struct
import cv2
import numpy as np
import ssl
import threading
import queue
import sys
import os
from dotenv import load_dotenv

load_dotenv()

IP_DESTINO = os.getenv('IP_DESTINO')
porta_raw = os.getenv('PORTA')

if IP_DESTINO is None or porta_raw is None:
    print("\nERRO CRÍTICO: 'IP_DESTINO' ou 'PORTA' não configurados no arquivo .env.")
    sys.exit(1)

try:
    PORTA = int(porta_raw)
except ValueError:
    print(f"\nERRO: Porta '{porta_raw}' inválida no arquivo .env.")
    sys.exit(1)

SEGREDO_COMPARTILHADO = os.getenv('SEGREDO_COMPARTILHADO', 'segredo_padrao_inseguro')

if SEGREDO_COMPARTILHADO == 'segredo_padrao_inseguro':
    print("AVISO CRÍTICO: Usando segredo inseguro. Verifique seu .env.")
else:
    print("Segredo compartilhado carregado.")

command_queue = queue.Queue()

def command_sender_thread(ssl_client, stop_event):
    while not stop_event.is_set():
        try:
            cmd = command_queue.get(timeout=0.5)
            ssl_client.sendall((cmd + '\n').encode('utf-8'))
        except queue.Empty:
            continue
        except (ConnectionResetError, BrokenPipeError, ssl.SSLError):
            break
        except Exception:
            break

def receive_data_thread(ssl_client, stop_event):
    cv2.namedWindow("Acesso Remoto", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Acesso Remoto", track_mouse_commands)
    tamanho_cabecalho = struct.calcsize(">L")

    while not stop_event.is_set():
        try:
            dados_tamanho = receber_dados_completo(ssl_client, tamanho_cabecalho)
            if not dados_tamanho: break
            
            tamanho_dados = struct.unpack(">L", dados_tamanho)[0]
            if tamanho_dados <= 0 or tamanho_dados > 20 * 1024 * 1024:
                break

            dados_video = receber_dados_completo(ssl_client, tamanho_dados)
            if not dados_video: break
            
            # CORREÇÃO CRÍTICA DE CODEC: Revertido para JPG para combinar com o Host
            nparr = np.frombuffer(dados_video, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                cv2.imshow("Acesso Remoto", frame)
            
            if cv2.waitKey(5) == 27: # Pressione ESC para sair
                stop_event.set()
                break
                
        except (ConnectionResetError, BrokenPipeError, ssl.SSLError):
            stop_event.set()
            break
        except Exception:
            stop_event.set()
            break
            
    cv2.destroyAllWindows()
    print("Sessão encerrada.")

def track_mouse_commands(evento, x, y, flags, param):
    if evento == cv2.EVENT_LBUTTONDOWN:
        command_queue.put(f"click,{x},{y}")

def receber_dados_completo(client_socket, qtd_bytes):
    bloco = b''
    try:
        while len(bloco) < qtd_bytes:
            dados = client_socket.recv(qtd_bytes - len(bloco))
            if not dados: return None
            bloco += dados
        return bloco
    except socket.error:
        return None

def start_secure_client():
    # BLINDAGEM SSL EXPLICITA PARA O CLIENTE
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 # Bloqueia protocolos antigos
    context.check_hostname = False # Obrigatório para certificados criados via IP
    context.verify_mode = ssl.CERT_NONE # Confia no certificado gerado localmente

    stop_event = threading.Event()
    ssl_client = None

    try:
        raw_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Conectando a {IP_DESTINO}:{PORTA}...")
        
        ssl_client = context.wrap_socket(raw_client, server_hostname=IP_DESTINO)
        ssl_client.settimeout(5.0) # Timeout para evitar travamento infinito se o IP não existir
        ssl_client.connect((IP_DESTINO, PORTA))
        ssl_client.settimeout(None) # Restaura para modo blocante após conectar
        
        print("Conexão SSL estabelecida.")

        ssl_client.sendall(SEGREDO_COMPARTILHADO.encode('utf-8'))
        auth_response_raw = receber_dados_completo(ssl_client, struct.calcsize(">L"))
        if not auth_response_raw:
             print("Sem resposta do servidor.")
             return

        auth_status = struct.unpack(">L", auth_response_raw)[0]
        if auth_status != 1:
            print("Falha na autenticação: Segredo incorreto.")
            return
        
        print("Autenticado com sucesso. Recebendo vídeo...")

        threads = [
            threading.Thread(target=command_sender_thread, args=(ssl_client, stop_event), daemon=True),
            threading.Thread(target=receive_data_thread, args=(ssl_client, stop_event))
        ]
        
        for t in threads: t.start()
        for t in threads: t.join()

    except Exception as e:
        print(f"Falha de conexão: {e}")
    finally:
        if ssl_client:
             try:
                 ssl_client.shutdown(socket.SHUT_RDWR)
                 ssl_client.close()
             except: pass

if __name__ == "__main__":
    start_secure_client()