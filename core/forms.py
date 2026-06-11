from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import User

from .models import SPACE_COLORS, Space, SpaceMembership


class SpaceForm(StyledFormMixin, forms.ModelForm):
    # Declared explicitly so the auto ModelForm field doesn't inject Django's
    # blank '---------' radio (the model field has no default).
    space_type = forms.ChoiceField(
        choices=Space.TYPE_CHOICES,
        initial=Space.TYPE_SOFTWARE,
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Space
        fields = ['space_type', 'name', 'key', 'description', 'color']
        widgets = {
            'key': forms.TextInput(attrs={
                'placeholder': 'e.g. CLIC', 'maxlength': 10,
                'class': 'input uppercase', 'x-on:input': '$el.value = $el.value.toUpperCase()',
            }),
            'description': forms.Textarea(attrs={'rows': 3}),
            'color': forms.RadioSelect(choices=[(c, c) for c in SPACE_COLORS]),
        }

    def clean_key(self):
        return self.cleaned_data['key'].upper()


class AddMemberForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label='Email of an existing AtlasHub user',
                             widget=forms.EmailInput(attrs={'placeholder': 'teammate@example.com'}))
    role = forms.ChoiceField(choices=SpaceMembership.ROLE_CHOICES,
                             initial=SpaceMembership.ROLE_MEMBER)

    def __init__(self, *args, space=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.space = space

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        try:
            self.cleaned_data['user'] = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            raise forms.ValidationError('No active account with that email — ask them to sign up first.')
        if self.space and self.space.memberships.filter(user=self.cleaned_data['user']).exists():
            raise forms.ValidationError('They are already a member of this space.')
        return email
