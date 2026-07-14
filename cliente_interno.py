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
import time
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
        except Exception as e:
            print(f"[!] Erro inesperado ao enviar comando: {e}")
            break

def receive_data_thread(ssl_client, stop_event):
    cv2.namedWindow("Acesso Remoto", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Acesso Remoto", track_mouse_commands)
    tamanho_cabecalho = struct.calcsize(">L")

    while not stop_event.is_set():
        try:
            dados_tamanho = receber_dados_completo(ssl_client, tamanho_cabecalho)
            if not dados_tamanho: 
                break
            
            tamanho_dados = struct.unpack(">L", dados_tamanho)[0]
            if tamanho_dados <= 0 or tamanho_dados > 20 * 1024 * 1024:
                break

            dados_video = receber_dados_completo(ssl_client, tamanho_dados)
            if not dados_video: 
                break
            
            # Decodificação do frame em JPG
            nparr = np.frombuffer(dados_video, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if frame is not None:
                cv2.imshow("Acesso Remoto", frame)
            
            # CORREÇÃO: Detecta se apertou ESC (27) OU se o usuário fechou a janela no 'X'
            if cv2.waitKey(5) == 27 or cv2.getWindowProperty("Acesso Remoto", cv2.WND_PROP_VISIBLE) < 1:
                stop_event.set()
                break
                
        except (ConnectionResetError, BrokenPipeError, ssl.SSLError):
            stop_event.set()
            break
        except Exception as e:
            print(f"[!] Erro na recepção de vídeo: {e}")
            stop_event.set()
            break
            
    cv2.destroyAllWindows()
    print("Sessão visual encerrada.")

def track_mouse_commands(evento, x, y, flags, param):
    if evento == cv2.EVENT_LBUTTONDOWN:
        command_queue.put(f"click,{x},{y}")

def receber_dados_completo(client_socket, qtd_bytes):
    bloco = b''
    try:
        while len(bloco) < qtd_bytes:
            dados = client_socket.recv(qtd_bytes - len(bloco))
            if not dados: 
                return None
            bloco += dados
        return bloco
    except socket.error:
        return None

def start_secure_client():
    # CORREÇÃO: Nova sintaxe SSL para remover o aviso de Deprecation
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2 # Bloqueia protocolos antigos e inseguros
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    stop_event = threading.Event()
    ssl_client = None

    try:
        raw_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"Conectando a {IP_DESTINO}:{PORTA}...")
        
        ssl_client = context.wrap_socket(raw_client, server_hostname=IP_DESTINO)
        ssl_client.settimeout(5.0)
        ssl_client.connect((IP_DESTINO, PORTA))
        ssl_client.settimeout(None)
        
        print("Conexão SSL estabelecida.")

        ssl_client.sendall((SEGREDO_COMPARTILHADO + '\n').encode('utf-8'))
        
        auth_response_raw = receber_dados_completo(ssl_client, struct.calcsize(">L"))
        if not auth_response_raw:
             print("Sem resposta do servidor durante autenticação.")
             return

        auth_status = struct.unpack(">L", auth_response_raw)[0]
        if auth_status != 1:
            print("Falha na autenticação: Segredo incorreto.")
            return
        
        print("Autenticado com sucesso. Recebendo vídeo...")
        print("DICA: Pressione 'ESC' na janela de vídeo ou feche no 'X' para sair.")

        threads = [
            threading.Thread(target=command_sender_thread, args=(ssl_client, stop_event), daemon=True),
            threading.Thread(target=receive_data_thread, args=(ssl_client, stop_event))
        ]
        
        for t in threads: 
            t.start()
            
        # CORREÇÃO: Substitui o t.join() por um loop que permite ler o Ctrl+C
        while not stop_event.is_set():
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n[*] Desligamento manual solicitado (Ctrl+C). Fechando conexões...")
        stop_event.set()
    except Exception as e:
        print(f"Falha de conexão: {e}")
    finally:
        if ssl_client:
             try:
                 ssl_client.shutdown(socket.SHUT_RDWR)
                 ssl_client.close()
             except Exception: 
                 pass

if __name__ == "__main__":
    start_secure_client()