# Audio- und Wallet-Dienste

RTKit gehört zu den Paketen für Updates, bestehende Arch-Installationen und neue
ISOs. PipeWire und pipewire-pulse können damit ihre Audio-Threads über D-Bus mit
Echtzeitpriorität anfordern. RTKit wird über D-Bus aktiviert; ein dauerhaftes
`systemctl enable` ist für diesen Dienst nicht erforderlich. Nach Installation
neu anmelden oder neu starten, damit die Audio-Dienste ihre Priorität neu anfordern.

Der frühere Installer schrieb `[Wallet] Enabled=false`. KDE wählt jedoch KWallet
als Secret-Portal. Bei deaktiviertem Wallet beendet sich dessen `ksecretd` mit
Fehlerstatus, statt den angeforderten Dienst bereitzustellen.

Neue Installationen aktivieren KWallet. Bei vorhandenen Installationen korrigiert
`configure_wallet.py` die Einstellung einmal im Konto `saar`, mit Sicherung der
alten Konfigurationsdatei. Der Marker liegt unter
`~/.local/state/saar-fighters/kwallet-enabled-v1`. Spätere persönliche Änderungen
werden bei Updates nicht überschrieben. Die Migration läuft beim aktualisierten
Oberflächenupdater und beim ersten Login nach dem Update, auch mit altem Updater.

Wallet-Inhalte, Passwörter und Browserprofile werden nicht gelesen oder verändert.
Es wird kein Wallet mit leerem Passwort erzeugt und keine automatische Entsperrung
eingerichtet. Beim ersten Zugriff kann der normale KDE-Einrichtungs- oder
Entsperrdialog erscheinen. `kwallet-pam` würde ohne eingegebenes Anmeldepasswort
beim automatischen Login keine automatische Entsperrung lösen und wird deshalb
nicht als vermeintliche Reparatur installiert.

Diese Änderung behandelt den KWallet-Startfehler. Andere Portal-Meldungen über
App-Registrierung haben andere Ursachen und werden dadurch nicht pauschal behoben.

Referenzen: [PipeWire RT](https://docs.pipewire.org/page_module_rt.html),
[KDE ksecretd](https://github.com/KDE/kwallet/blob/master/src/runtime/ksecretd/main.cpp).
