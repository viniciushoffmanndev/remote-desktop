import socket
import struct
import mss
import pyautogui
import threading
import cv2
import numpy as np
import time
import ssl
import os
import sys
import hmac
import select
from dotenv import load_dotenv

load_dotenv()

IP_LOCAL = os.getenv('IP_LOCAL', '0.0.0.0')
porta_raw = os.getenv('PORTA')

if porta_raw is None:
    print("\nERRO CRÍTICO: 'PORTA' não configurada no arquivo .env.")
    sys.exit(1)

try:
    PORTA = int(porta_raw)
except ValueError:
    print(f"\nERRO: Porta '{porta_raw}' inválida no arquivo .env.")
    sys.exit(1)

SEGREDO_COMPARTILHADO = os.getenv('SEGREDO_COMPARTILHADO', 'segredo_padrao_inseguro')

pyautogui.FAILSAFE = False

if SEGREDO_COMPARTILHADO == 'segredo_padrao_inseguro':
     print("AVISO CRÍTICO: Usando segredo inseguro. Verifique seu .env.")
else:
     print("Segredo compartilhado carregado com sucesso.")

def tratar_autenticacao(ssl_conn):
    try:
        # 1. Previne Port Scan/Slowloris: Máximo de 8 segundos para mandar a senha
        ssl_conn.settimeout(8.0) 
        
        # 3. Resolve a Fragmentação TCP na leitura da senha
        buffer = ""
        while '\n' not in buffer:
            chunk = ssl_conn.recv(1024).decode('utf-8')
            if not chunk:
                return False
            buffer += chunk
            
        dados_auth = buffer.split('\n')[0].strip()
        
        # 2. Previne Timing Attacks comparando os hashes de forma segura
        if hmac.compare_digest(dados_auth, SEGREDO_COMPARTILHADO):
            ssl_conn.sendall(struct.pack(">L", 1))
            ssl_conn.settimeout(None) # Remove o timeout para não atrapalhar o vídeo
            return True
        else:
            ssl_conn.sendall(struct.pack(">L", 0))
            return False
            
    except socket.timeout:
        print("Autenticação falhou: Cliente demorou muito para responder (Timeout).")
        return False
    except Exception as e:
        print(f"Erro na autenticação: {e}")
        return False
    finally:
        # Garante que, independente do erro, o socket não fique com timeout preso caso sobreviva
        ssl_conn.settimeout(None)

def tratar_comandos(conexao, stop_event):
    buffer = ""
    while not stop_event.is_set():
        try:
            # 6. Resolve o Timeout Global espiando a rede sem alterar configurações do socket
            ready_to_read, _, _ = select.select([conexao], [], [], 1.0)
            
            if ready_to_read:
                dados = conexao.recv(1024).decode('utf-8')
                if not dados:
                    break
                    
                buffer += dados
                if '\n' in buffer:
                    linhas = buffer.split('\n')
                    buffer = linhas.pop()
                    
                    for linha in linhas:
                        if not linha.strip():
                            continue
                        partes = linha.split(',')
                        if len(partes) == 3:
                            cmd, x, y = partes
                            try:
                                x, y = int(x), int(y)
                                if cmd == "click": 
                                    pyautogui.click(x, y)
                                elif cmd == "move": 
                                    pyautogui.moveTo(x, y)
                            except ValueError:
                                # 5. Corrige o Silenciamento Inseguro informando o erro
                                print(f"[!] Aviso: coordenadas inválidas recebidas: {partes}")
        except (ConnectionResetError, ConnectionAbortedError, ssl.SSLError):
            break
        except Exception as e:
            print(f"[!] Erro inesperado na thread de comandos: {e}")
            break

def iniciar_host():
    raw_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    raw_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    raw_server.bind((IP_LOCAL, PORTA))
    raw_server.listen(1)
    
    print(f"[*] Host iniciado na porta {PORTA}. Aguardando conexão...")

    while True:
        raw_conn, addr = raw_server.accept()
        print(f"\n[+] Conexão de rede estabelecida com {addr}")

        ssl_server = None
        try:
            # BLINDAGEM SSL EXPLICITA PARA O SERVIDOR
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            
            # CARREGAMENTO OBRIGATÓRIO DOS CERTIFICADOS
            if not os.path.exists("server.crt") or not os.path.exists("server.key"):
                print("ERRO: Arquivos server.crt ou server.key não encontrados!")
                raw_conn.close()
                continue
                
            context.load_cert_chain(certfile="server.crt", keyfile="server.key")

            ssl_server = context.wrap_socket(raw_conn, server_side=True)
            print("Conexão SSL estabelecida.")
            
            if not tratar_autenticacao(ssl_server):
                print("Autenticação falhou. Derrubando cliente.")
                ssl_server.shutdown(socket.SHUT_RDWR)
                ssl_server.close()
                continue
            
            print("Acesso remoto autorizado e iniciado.")
            stop_event = threading.Event()
            
            thread_cmd = threading.Thread(target=tratar_comandos, args=(ssl_server, stop_event), daemon=True)
            thread_cmd.start()
            
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                while not stop_event.is_set():
                    img = sct.grab(monitor)
                    img_np = np.array(img)
                    
                    # Usa qualidade 60 para JPEG para garantir fluidez extrema na LAN
                    _, img_encoded = cv2.imencode('.jpg', img_np, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                    dados_bytes = img_encoded.tobytes()
                    
                    pacote = struct.pack(">L", len(dados_bytes)) + dados_bytes
                    ssl_server.sendall(pacote)
                    
                    # 4. Resolve o Fritador de CPU limitando a ~30 FPS
                    time.sleep(1 / 30)
                    
        except (ConnectionResetError, BrokenPipeError, ssl.SSLError) as e:
            print(f"[-] Cliente desconectado. Motivo: {e}")
        except Exception as e:
            print(f"[!] Falha crítica: {e}")
        finally:
            if ssl_server:
                stop_event.set()
                try:
                    ssl_server.shutdown(socket.SHUT_RDWR)
                    ssl_server.close()
                except Exception as e:
                    print(f"[!] Erro ao fechar conexão SSL: {e}")
            time.sleep(0.5)

if __name__ == "__main__":
    try:
        iniciar_host()
    except KeyboardInterrupt:
        print("\n[*] Servidor encerrado (Ctrl+C).")