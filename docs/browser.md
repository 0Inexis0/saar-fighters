# Brave als Dashboard-Browser

Internet, YouTube, Vereinswebseite, der Spotify-Web-Fallback und Rocket Launch
verwenden denselben Brave-Startbefehl. Eine vorhandene native Brave-Installation
wird bevorzugt. Sonst verwendet das System die von Brave gepflegte Flathub-App
`com.brave.Browser`, passend zur bereits vorhandenen Flatpak-Verwaltung.

Systemupdates installieren Brave bei Bedarf und setzen danach die HTTP-, HTTPS-
und HTML-Zuordnungen für den Benutzer `saar`. Schlägt die Installation fehl,
bleiben die bisherigen Browserzuordnungen bestehen. Das Update meldet einen
Fehler. Neue ISO-Builds enthalten Brave statt Firefox.

Firefox wird bei bestehenden Installationen nicht während einer laufenden Sitzung
deinstalliert. Seine Profile, Lesezeichen und Anmeldungen bleiben unverändert.
Brave beginnt mit seinem eigenen Profil; eine Übernahme persönlicher Browserdaten
wird nicht automatisch durchgeführt.

Es werden keine Sandbox-Flags abgeschaltet. Der Browserwechsel allein ist kein
Nachweis, dass die zuvor beobachteten Abstürze behoben sind. Video, Musik und das
lokale Rocket-Spiel müssen nach Installation auf dem Laptop geprüft werden.

[Braves Linux-Installationswege und Hinweise zur Flatpak-Ausgabe](https://brave.com/linux/).
