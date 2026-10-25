# SSH-Fernwartung im lokalen Netz

Der System-Update-Knopf installiert OpenSSH und richtet einen eigenen Dienst
`saar-sshd.service` auf Port **2222** ein. Die Anmeldung erfolgt als `wartung`
mit dem zum öffentlichen Schlüssel unter `system/ssh/support_ed25519.pub`
gehörenden privaten Schlüssel. Passwortanmeldung und Root-Anmeldung sind gesperrt.

## Auf einem bereits installierten Vereinslaptop

1. Unter Einstellungen das Systemupdate ausführen und auf Erfolg warten.
2. Bei Versionen ohne diese SSH-Erweiterung das Systemupdate **ein zweites Mal**
   ausführen. Der erste Durchlauf ersetzt den alten Updater. Erst dessen nächster
   Aufruf kann OpenSSH installieren und den neuen Einrichtungsschritt starten.
3. Die Update-Ausgabe zeigt die lokale IP-Adresse und den Hostschlüssel-Fingerabdruck.

Es ist kein Terminalbefehl und kein Neustart auf dem Laptop nötig. Beide Geräte
müssen im selben erreichbaren lokalen Netz sein; Gast-WLAN und Client-Isolation
können Verbindungen verhindern. Die vorhandene Passwortfreigabe des Systemupdates
bleibt erforderlich. Ein Fehler beim SSH-Start lässt den Update-Lauf fehlschlagen.

Auf dem Wartungsrechner:

```sh
ssh -i ~/.ssh/saar_fighters_support_ed25519 -p 2222 wartung@LAPTOP-IP
```

Der private Schlüssel wird ausschließlich auf dem Wartungsrechner aufbewahrt.
Der erstmalige Hostschlüssel kann mit dem Fingerabdruck in der Update-Ausgabe
verglichen werden. Spätere Änderungen an diesem Schlüssel müssen geprüft werden.

## Firefox untersuchen

Nach der SSH-Anmeldung liefert dieser feste Befehl ohne zusätzliche Passwortabfrage
einen JSON-Bericht:

```sh
sudo -n /usr/local/libexec/saar-diagnose-firefox
```

Er liest Paketversionen, RAM/Swap, Grafikgeräte, passende Kernelmeldungen aus dem
aktuellen und vorherigen Start sowie ausgewählte Metadaten der letzten zehn
lokalen Firefox-Absturzberichte. Browser-URLs, Cookies, Passwörter, Sitzungsdateien
und rohe Speicherabbilder werden nicht ausgelesen. Es erfolgt kein Upload.
Andere Administratorbefehle benötigen weiterhin das Wartungspasswort.

## Geltungsbereich und Abschalten

- Zugelassen sind IPv4-Quellen aus `10.0.0.0/8`, `172.16.0.0/12`,
  `192.168.0.0/16` und localhost. IPv6 ist für diesen Dienst deaktiviert.
- Es werden keine Routerfreigaben, Cloud-Tunnel oder VPN-Konten eingerichtet.
- Der normale `sshd`-Dienst und seine Konfiguration werden nicht verändert.
- Im Live-ISO bleibt die Fernwartung aus. Sie wird auf installierten Systemen
  beim Systemupdate aktiviert und startet anschließend auch nach einem Neustart.
- Der enthaltene öffentliche Schlüssel gehört dem Betreiber dieses Repositorys.
  **Wer das Projekt für eigene Rechner übernimmt, muss ihn vor dem Update durch
  den eigenen öffentlichen Schlüssel ersetzen.** Eine Kopie des Repositorys
  erhält keinen privaten Schlüssel, installiert aber sonst dieselbe Zugangsberechtigung.

Die Administration kann die Fernwartung dauerhaft ausschalten:

```sh
sudo touch /etc/saar-fighters/ssh/disabled
sudo systemctl disable --now saar-sshd.service
```

Weitere Updates respektieren diese Datei. Zum erneuten Aktivieren wird sie durch
die Administration entfernt und das Systemupdate ausgeführt.

## Prüfgrenzen

Die automatisierten Tests prüfen Dateieinrichtung, Wiederholung, Opt-out,
Live-System-Sperre und Fehlerfälle. Der Linux-Integrationstest startet einen echten
OpenSSH-Server mit temporären Testschlüsseln und testet erfolgreiche und abgewiesene
Anmeldungen. Das ersetzt keine Verbindung zum konkreten Vereinslaptop.
