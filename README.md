<div align="center">

<img src="app/assets/club-logo.gif" width="80" alt="Saar-Fighters AS e.V.">

# Saar-Fighters OS

**Der einfache Vereinsdesktop auf Arch Linux.**

[![Version](https://img.shields.io/badge/Version-0.2.0-a5a77a?style=flat-square)](https://github.com/0Inexis0/saar-fighters/releases/latest)
![Arch Linux](https://img.shields.io/badge/Arch_Linux-x86__64-35372c?style=flat-square&logo=archlinux&logoColor=c3b48b)
![Sprache](https://img.shields.io/badge/Sprache-Deutsch-35372c?style=flat-square)

[**ISO herunterladen**](https://github.com/0Inexis0/saar-fighters/releases/latest) · [Installation](docs/installation.md) · [Verein](https://www.saarfighters-as.de/)

</div>

![Saar-Fighters Desktop](docs/desktop.png)

Spotify, Firefox, Dateien und Airsoft Rocket Launch auf einen Klick. Die Spielkonsole startet lokal und offline über ihre eigene Kachel. WLAN, Bluetooth, Lautstärke und Updates gemeinsam in der Kachel „Einstellungen“. Matte Olive-Optik, große Buttons und gemeinsame Updates für System und Oberfläche.

## Loslegen

**Neuer Rechner:** Im [Release](https://github.com/0Inexis0/saar-fighters/releases/latest) das Download-Skript starten. Es lädt und verbindet die ISO-Teile automatisch. Die fertige ISO auf einen USB-Stick schreiben, starten und installieren – Spotify ist dabei, die Installation geht offline.

**Arch bereits installiert:**

```bash
curl -fsSL https://raw.githubusercontent.com/0Inexis0/saar-fighters/main/system/setup-arch.sh | sudo bash
```

Der Einzeiler fragt vor Änderungen nach und formatiert keine Laufwerke. Das Wartungspasswort legst du selbst fest. Updates benötigen keinen GitHub-Login.

> **ISO:** x86_64 · 4 GB RAM · 32 GB Laufwerk · USB ab 8 GB · Secure Boot aus. Der grafische Installer löscht das ausgewählte Ziellaufwerk.

---

[Installation im Detail](docs/installation.md) · [Bildnachweise](docs/assets.md) · [MIT-Lizenz](LICENSE)

[Entwicklung & Wartung](docs/handbook.md) · [Prüfprotokoll](docs/iso-validation-0.2.0.md)
