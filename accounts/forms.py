from django import forms


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Benutzername", max_length=150, widget=forms.TextInput(attrs={"autofocus": True})
    )
    password = forms.CharField(label="Passwort", strip=False, widget=forms.PasswordInput)


class CodeForm(forms.Form):
    code = forms.CharField(
        label="Code",
        max_length=32,
        widget=forms.TextInput(
            # No numeric keyboard: recovery codes contain letters.
            attrs={"autocomplete": "one-time-code", "autofocus": True}
        ),
    )
