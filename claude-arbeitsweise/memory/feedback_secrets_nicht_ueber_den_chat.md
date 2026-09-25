---
name: secrets-nicht-ueber-den-chat
description: "Dauerhafte Tokens per verdecktem read-Befehl in die .env, Claude liest sie von dort"
metadata:
  type: feedback
---

Zugangsdaten ohne Ablaufdatum nicht über den Chat einsammeln. Dem Nutzer einen Befehl geben, der den Wert verdeckt abfragt und selbst einträgt:

```
read -rsp 'Token: ' T && echo && python3 -c "import sys,pathlib; p=pathlib.Path('<pfad>/.env'); z=p.read_text().splitlines(True); i=[i for i,l in enumerate(z) if l.startswith('<SCHLUESSEL>=')]; z[i[0]]='<SCHLUESSEL>='+sys.argv[1].strip()+chr(10) if i else z.append('<SCHLUESSEL>='+sys.argv[1].strip()+chr(10)); p.write_text(''.join(z)); print('eingetragen')" "$T"
```

**Why:** Ein im Chat geschickter Token steht danach im Transkript und in jedem Export. Ein Neustart, der per `&&` an den Befehl gehängt war, brach einmal ab, und der Dienst lief eine Stunde mit dem alten Wert weiter, was nach kaputtem Token aussah.

**How to apply:** Den Neustart nicht an den Befehl hängen, sondern selbst auslösen und dabei Dateizeit gegen Startzeit des Prozesses prüfen. Secrets nie in Ausgaben, Commits oder Repo-Dateien.
