<p align="center">
  <img src="https://img.shields.io/badge/PYTHON-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/OPENCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" />
  <img src="https://img.shields.io/badge/SSL%20/%20TLS-009688?style=for-the-badge&logo=letsencrypt&logoColor=white" />
  <img src="https://img.shields.io/badge/PYAUTOGUI-FF6F61?style=for-the-badge&logo=python&logoColor=white" />
</p>

<h2 align="center">🖥️ Remote Desktop — Secure Control Hub 🖥️</h2>

---

## 🎯 Objetivo do Projeto

Um sistema ultraveloz e seguro de controle e visualização de desktop remoto desenvolvido em Python. Projetado para redes locais (LAN), o projeto estabelece uma conexão cliente-servidor robusta baseada em sockets criptografados nativamente com segurança de transporte TLS 1.2 e autenticação simétrica contra ataques de temporização (*timing attacks*). O host transmite capturas de tela fluidas enquanto interpreta cliques e ações periféricas recebidas diretamente do painel do cliente.

---

## ✨ Funcionalidades

* **Transmissão Fluida de Tela (30 FPS)**: Uso do wrapper de captura nativo de alta velocidade `mss` integrado à decodificação de imagem em memória do OpenCV, limitando o estresse de CPU no host através de compressão dinâmica para JPEG com qualidade otimizada.
* **Criptografia TLS 1.2 de Ponta a Ponta**: Camada de rede blindada por meio do módulo `ssl`, exigindo carregamento obrigatório de cadeia de certificados locais (`server.crt`/`server.key`) e restringindo protocolos legados ou inseguros.
* **Autenticação Resiliente `hmac`**: Prevenção ativa contra ataques de dicionário e de força bruta através do método seguro `hmac.compare_digest` para validação do segredo compartilhado.
* **Segurança de Conexão e Port-Scanning**: Mecanismos de timeout estrito (máximo de 8 segundos para envio da credencial) que previnem conexões fantasmas (*Slowloris*) e travamentos de socket por fragmentação TCP.
* **Interação Direta e Mouse-Tracking**: Mapeamento e encapsulamento em tempo real de cliques via fila de execução (`queue.Queue`) e simulação instantânea de mouse no sistema operacional do host utilizando PyAutoGUI.
* **Resiliência de Encerramento**: Interrupção limpa de conexões (`socket.SHUT_RDWR`) e descarte ordenado de threads tanto via comandos visuais (pressionando a tecla `ESC` ou fechando a janela de vídeo) quanto por desligamento via terminal (`Ctrl+C`).

### 📊 Arquitetura de Conexão Direta

```mermaid
graph TD
    subgraph PC_Admin [PC Administrador - Cliente]
        C[client.py] -->|1. Conecta via SSL| H
        C -->|3. Envia Comandos de Clique| H
        H -->|4. Transmite Frames de Vídeo| C
    end
    
    subgraph PC_Usuario [PC Usuário - Host]
        H[host.py / host.exe]
        EnvH[.env: IP_LOCAL=0.0.0.0] --> H
        Crt[server.crt / server.key] --> H
    end
    
    EnvC[.env: IP_DESTINO=IP_DO_HOST] --> C

```