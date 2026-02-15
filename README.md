# 💼 Portfolio-Manager

> Professionelle Desktop-Anwendung für Aktien-, ETF- und Krypto-Portfolio-Verwaltung

Portfolio-Manager für Windows mit Fokus auf einfache Erfassung, Performance-Überblick und lokale Datenspeicherung.

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-brightgreen.svg)
![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-orange.svg)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)

## ✨ Features

### Aktuelle Funktionen
- ✅ Portfolio-Tracking für bis zu 10 Assets
- ✅ Manuelle Kurseingabe
- ✅ Gewinn/Verlust-Berechnung
- ✅ Basis-Charts und Diagramme
- ✅ CSV Import/Export
- ✅ Automatische Backups

## 📸 Screenshots

![Portfolio Übersicht](docs/images/screenshot_portfolio.svg)
![Performance Chart](docs/images/screenshot_chart.svg)
![Dividenden Tracking](docs/images/screenshot_dividends.svg)

## 🚀 Installation

### Option 1: Windows Installer (Empfohlen)
1. Öffne die Release-Seite: [GitHub Releases](https://github.com/xKrikZ/MeinPortfolio-App/releases)
2. Lade im neuesten Release die Setup-Datei (`*.exe`) aus **Assets** herunter.
3. Doppelklick auf die .exe
4. Folge dem Installations-Assistenten
5. Fertig! 🎉

Hinweis: Falls noch kein Release vorhanden ist, gibt es noch keine `*.exe`-Datei.

Sofort verfügbar (ohne Release):
- Quellcode als ZIP: [MeinPortfolio-App-main.zip](https://github.com/xKrikZ/MeinPortfolio-App/archive/refs/heads/main.zip)

### Option 2: Von Quellcode (Entwickler)
Hinweis: Markdown-Zeilen wie `# ...`, `## ...`, `- ...` oder `![...]` werden nicht im Terminal ausgeführt.
Führe nur die Befehle innerhalb des Codeblocks aus.

```bash
# Repository klonen und in den Ordner wechseln
git clone https://github.com/xKrikZ/MeinPortfolio-App.git
cd MeinPortfolio-App

# Virtual Environment erstellen
python -m venv venv
venv\Scripts\activate

# Dependencies installieren
pip install -r requirements.txt

# Anwendung starten
python main.py
```

## 📄 Lizenz

Dieses Projekt ist unter der **PolyForm Noncommercial License 1.0.0** lizenziert und darf ausschließlich nicht-kommerziell genutzt werden.
Die vollständigen Lizenzbedingungen findest du in [LICENSE](LICENSE).