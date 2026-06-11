from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from .models import NotificationPreference, User


class StyledFormMixin:
    """Apply the shared Tailwind input class to every visible widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'checkbox')
            else:
                widget.attrs.setdefault('class', 'input')


class SignupForm(StyledFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label='Password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirm password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone']
        widgets = {
            'email': forms.EmailInput(attrs={'autocomplete': 'email', 'autofocus': True}),
            'phone': forms.TextInput(attrs={
                'autocomplete': 'tel', 'placeholder': 'e.g. 071 684 3608 or +27 71 684 3608',
            }),
        }

    def clean_email(self):
        return self.cleaned_data['email'].lower()

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("The passwords don't match.")
        return p2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get('password1')
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error('password1', error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class LoginForm(StyledFormMixin, AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Email'
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'email', 'autofocus': True, 'placeholder': 'you@example.com',
        })

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': 'Incorrect email address or password.',
    }


class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']
        widgets = {
            'phone': forms.TextInput(attrs={
                'autocomplete': 'tel', 'placeholder': 'e.g. 071 684 3608 or +27 71 684 3608',
            }),
        }


class NotificationPreferenceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            'notify_issue_assigned', 'notify_mention',
            'notify_sprint_started', 'notify_sprint_completed',
        ]
