# 💼 Portfolio-Manager

> Professionelle Desktop-Anwendung für Aktien-, ETF- und Krypto-Portfolio-Verwaltung

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)

## ✨ Features

### Kostenlose Version
- ✅ Portfolio-Tracking für bis zu 10 Assets
- ✅ Manuelle Kurseingabe
- ✅ Gewinn/Verlust-Berechnung
- ✅ Basis-Charts und Diagramme
- ✅ CSV Import/Export
- ✅ Automatische Backups

### Premium Version
- ⭐ Unbegrenzte Assets
- ⭐ Dividenden-Tracking
- ⭐ Benchmark-Vergleich (Alpha, Beta, Sharpe Ratio)
- ⭐ Preisalarme mit Desktop-Benachrichtigungen
- ⭐ Automatische Kurs-Updates (API)
- ⭐ Multi-Währungs-Support
- ⭐ Performance-Analyse
- ⭐ Bulk-Import
- ⭐ Priority Support

## 📸 Screenshots

![Portfolio Übersicht](docs/images/screenshot_portfolio.png)
![Performance Chart](docs/images/screenshot_chart.png)
![Dividenden Tracking](docs/images/screenshot_dividends.png)

## 🚀 Installation

### Option 1: Windows Installer (Empfohlen)
1. Download: [PortfolioManager-Setup-v1.0.0.exe](https://github.com/IhrUsername/portfolio-manager/releases/latest)
2. Doppelklick auf die .exe
3. Folge dem Installations-Assistenten
4. Fertig! 🎉

### Option 2: Portable Version
1. Download: [PortfolioManager-v1.0.0-Portable.zip](https://github.com/IhrUsername/portfolio-manager/releases/latest)
2. Entpacke das ZIP
3. Führe `PortfolioManager.exe` aus

### Option 3: Von Quellcode (Entwickler)
Hinweis: Markdown-Zeilen wie `# ...`, `## ...`, `- ...` oder `![...]` werden nicht im Terminal ausgeführt.
Führe nur die Befehle innerhalb des Codeblocks aus.

```bash
# In den Projektordner wechseln (anpassen falls dein Pfad anders ist)
cd C:\Users\Janni\OneDrive\Desktop\Private\Privatbereich\Aktien

# Virtual Environment erstellen
python -m venv venv
venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt

# Anwendung starten
python main.py
```

Optional (nur wenn du wirklich von GitHub klonen willst):

```bash
git clone https://github.com/<USERNAME>/<REPO>.git
cd <REPO>
```