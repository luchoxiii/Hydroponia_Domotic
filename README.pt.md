# 🌱 HydroControl - Sistema Integral de Controle, IA e Telemetria para Hidroponia

<p align="center">
  🌍 <strong>Idioma / Language / Langue:</strong><br>
  <a href="README.md"><img src="https://img.shields.io/badge/🇪🇸_Español-Leer-0d6efd?style=for-the-badge" alt="Español"></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/🇺🇸_English-Read-0d6efd?style=for-the-badge" alt="English"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-Lire-6f42c1?style=for-the-badge" alt="Français"></a>
  <a href="README.pt.md"><img src="https://img.shields.io/badge/🇧🇷_Português-Ativo-198754?style=for-the-badge" alt="Português"></a>
</p>

<p align="center">
  <img src="docs/img/hero_hydrocontrol.png" alt="HydroControl Smart Hydroponics &amp; Mushrooms" width="100%" style="border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.25);">
</p>

<p align="center">
  <a href="https://github.com/luchoxiii/Hydroponia_Domotic"><img src="https://img.shields.io/badge/GitHub-Hydroponia__Domotic-181717?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Repository"></a>
  <a href="https://github.com/luchoxiii"><img src="https://img.shields.io/badge/Author-luchoxiii-0A66C2?style=for-the-badge&logo=github&logoColor=white" alt="Author luchoxiii"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge&logo=open-source-initiative&logoColor=white" alt="License MIT"></a>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Flask-3.1.0-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask 3.1.0">
  <img src="https://img.shields.io/badge/i18n-ES%20%7C%20EN%20%7C%20FR%20%7C%20PT-0dcaf0?style=for-the-badge&logo=googletranslate&logoColor=white" alt="i18n Multilíngue">
  <img src="https://img.shields.io/badge/Production-Waitress%20WSGI-success?style=for-the-badge&logo=server&logoColor=white" alt="Waitress WSGI">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Ready">
  <img src="https://img.shields.io/badge/SQLite-WAL%20Mode-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite WAL">
  <img src="https://img.shields.io/badge/Machine%20Learning-Random%20Forest-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" alt="Scikit-Learn">
  <img src="https://img.shields.io/badge/IoT-ESP32%20%7C%20Arduino-00979D?style=for-the-badge&logo=arduino&logoColor=white" alt="IoT Ready">
  <img src="https://img.shields.io/badge/Telegram-Dual%20Bot%20API-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram API">
  <img src="https://img.shields.io/badge/Discord-Rich%20Embeds-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord Webhook">
  <img src="https://img.shields.io/badge/Auditoria-AES--256%20Criptografada-darkblue?style=for-the-badge&logo=lock&logoColor=white" alt="Registro Criptografado">
  <img src="https://img.shields.io/badge/Tests-120%20Passed-success?style=for-the-badge&logo=pytest&logoColor=white" alt="120 Pytest Passed">
</p>

<p align="center">
  🌐 <strong>Repositório Oficial:</strong> <a href="https://github.com/luchoxiii/Hydroponia_Domotic">github.com/luchoxiii/Hydroponia_Domotic</a> &nbsp;|&nbsp; 👤 <strong>Autor &amp; Titular dos Direitos:</strong> <a href="https://github.com/luchoxiii">luchoxiii</a>
</p>

---

## ⚙️ Como Funciona o Sistema?

O **HydroControl** é uma plataforma aberta de software e hardware projetada para operar estufas comerciais, fazendas verticais e cultivos domésticos de hidroponia e fungicultura (cogumelos). Ele coordena em tempo real a ingestão de telemetria de microcontroladores (ESP32, Arduino, Raspberry Pi), avalia os sinais vitais do cultivo contra um catálogo botânico e micológico de referência, executa diagnósticos preditivos com **Machine Learning (Random Forest)**, registra todas as operações em um **livro-razão de auditoria forense criptografado com AES-256 + HMAC**, e envia alertas através de canais independentes no **Telegram** e **Discord**.

---

## 🌟 Catálogo Completo de Funcionalidades

### 1. 📚 Catálogo Botânico e Micológico (Plantas e Fungos)
Inclui de fábrica **15 espécies pré-calibradas** e permite cadastrar novas espécies personalizadas:
* **🌱 Plantas Hidropônicas**: Alface Butterhead, Manjericão, Tomate Cereja, Espinafre, Morango, Pimentão, Coentro, Hortelã, Rúcula, Couve Kale, Pepino.
* **🍄 Fungos Micológicos**: Champignon de Paris, Cogumelo Shimeji / Ostra (*Pleurotus ostreatus*), Shiitake, Juba de Leão (*Hericium erinaceus*).
* **Parâmetros Configuráveis por Espécie**: pH mín/máx, Condutividade Elétrica (EC em mS/cm), Temperatura (°C), Umidade Relativa (%), Fotoperíodo diário (horas de luz) e ciclo estimado até a colheita (dias).

### 2. 🌿 Ciclo de Vida e Gestão de Cultivos Ativos
* Cálculo dinâmico de dias ativos e barra de progresso percentual até a colheita.
* Máquina de estados: `ACTIVO` (Ativo), `PAUSADO` (Pausado), `COSECHADO` (Colhido).
* **Exclusão Segura em Cascata (`POST /cultivos/<id>/eliminar`)**: Desvincula os microcontroladores IoT associados (`cultivo_id = None`), remove leituras e alertas sob controle transacional ACID e registra o evento no log criptografado.

### 3. 🧠 Centro de Inteligência Artificial e Laboratório "What-If" (`/ml`)
* **Random Forest Classifier (100 árvores de decisão + `StandardScaler`)**: Treinado com 1.500 cenários agronômicos balanceados (**97,3% de acurácia**, **96,9% de F1-Score** e latência de inferência **< 2 ms** em memória RAM local).
* **5 Classes de Diagnóstico Fisiológico**:
  * `OPTIMO` (Ótimo / Saudável)
  * `ESTRES_TERMICO` (Estresse Térmico - Calor/Frio)
  * `ESTRES_HIDRICO` (Estresse Hídrico / Reservatório Baixo)
  * `DESBALANCE_NUTRICIONAL` (Desequilíbrio Nutricional / Bloqueio Iônico)
  * `RIESGO_PATOGENO` (Risco Patogênico / Fúngico)
* **Simulador Interativo "What-If" (`POST /api/ml/simular`)**: Controles deslizantes em tempo real e presets de 1 clique para simular variações químicas e microclimáticas antes de aplicá-las na estufa.
* **Modelo Fenológico Térmico de Colheita (GDD - Graus-Dia de Crescimento)**: Calcula o acúmulo térmico $\text{GDD} = \sum \max(0, T_{\text{média}} - T_{\text{base}})$ para projetar os dias restantes até a colheita.

### 4. 🌦️ Integração Bioclimática via Satélite (Open-Meteo)
* Consulta a API meteorológica **Open-Meteo** (sem necessidade de chave de API) com cache em memória de 10 minutos e estimador resiliente offline.
* Calcula os diferenciais térmico ($\Delta T$) e de umidade ($\Delta H$) entre o interior e o exterior para recomendar ventilação passiva, exaustão forçada ou umidificação ultrassônica.

### 5. 📁 Importação e Exportação em Massa via CSV
* Download instantâneo de todo o histórico em CSV (`/cultivos/<id>/exportar.csv` ou `/cultivos/<id>/exportar-csv`).
* Importação em lote compatível com **Formato Largo** e **Formato Longo**, com verificação automática de alertas.

### 6. 🔌 Plataforma IoT e Gerador de Firmware em 1 Clique
* **Download Direto de Firmware Arduino/ESP32 (`.ino`)**: Gera automaticamente o código C++ com a `api_key`, endereço IP/porta do servidor e credenciais Wi-Fi injetadas.
* **Simulador de Sensor Virtual em 1 Clique (`/dispositivos/simulador-virtual`)**: Injeta telemetria normal ou anomalias críticas para testar alertas e IA sem hardware físico conectado.

### 7. 💬 Arquitetura Dupla de Notificações e Telemetria
* **Bot 1 — Telemetria Privada do Desenvolvedor (`services/telemetria_dev.py`)**: Canal privado para o criador do software com UUID de instalação, SO, versão do Python, contagem de inicializações e consumo de recursos.
* **Bot 2 — Canais de Notificação do Usuário (`services/notificaciones_usuario.py` & `services/telegram_bot.py`)**: **Webhooks do Discord** (Embeds ricos) e **Bot Pessoal do Telegram** com comandos interativos (`/start`, `/status`, `/cultivos`, `/telemetria <id>`, `/clima`, `/alertas`).

### 8. 🔒 Registro de Auditoria Forense Criptografado e Imutável (`/bitacora`)
* Criptografia simétrica autenticada **Fernet (AES-128-CBC + HMAC-SHA256)** com derivação de chave **PBKDF2-HMAC-SHA256 (100.000 iterações)**.
* **Encadeamento Criptográfico de Hashes (SHA-256 Hash Chaining)** garantindo integridade contra qualquer tentativa de adulteração.

### 9. 🌍 Suporte Multilíngue Nativo (Espanhol, Inglês, Francês e Português)
* Motor de internacionalização integrado ([`services/i18n.py`](services/i18n.py)) com suporte para **Espanhol (`es`)**, **Inglês (`en`)**, **Francês (`fr`)** e **Português (`pt`)**.
* Seletor interativo na barra de navegação superior (`/idioma/<lang>` ou `/set-language/<lang>`), parâmetro `?lang=pt`, cookie persistente (`hydro_lang`), detecção automática via cabeçalho `Accept-Language` e endpoint JSON (`/api/i18n/<lang>`).

---

## 🚀 Início Rápido e Implantação em Produção

### Desenvolvimento Local
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
python seed_demo.py
python app.py
```

### Servidor WSGI de Produção (Waitress)
```bash
# Windows:
iniciar_produccion.bat
# Linux / Raspberry Pi:
./iniciar_produccion.sh
# Ou diretamente:
python wsgi.py
```

### Docker & Docker Compose
```bash
docker-compose up -d --build
```

### Suíte de Testes Automatizados (Pytest)
```bash
pytest -v
```

---

## 👤 Autor e Licença

* **Autor**: **luchoxiii** ([@luchoxiii](https://github.com/luchoxiii))
* **Repositório Oficial**: [https://github.com/luchoxiii/Hydroponia_Domotic](https://github.com/luchoxiii/Hydroponia_Domotic)
* **Licença**: Distribuído sob os termos da **Licença MIT**. Consulte o arquivo [`LICENSE`](LICENSE) para mais informações.
