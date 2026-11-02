from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    invite_code = forms.CharField(required=False, label="Invite code", widget=forms.PasswordInput(render_value=False))

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_invite_code(self):
        provided = self.cleaned_data.get("invite_code", "")
        required = settings.REGISTRATION_INVITE_CODE
        if required and provided != required:
            raise forms.ValidationError("That invite code is not valid.")
        return provided

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class CSVUploadForm(forms.Form):
    file = forms.FileField(label="Transaction CSV", help_text="CSV only · up to 8 MB")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > 8 * 1024 * 1024:
            raise forms.ValidationError("Choose a CSV under 8 MB.")
        if not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Choose a .csv file.")
        return uploaded
