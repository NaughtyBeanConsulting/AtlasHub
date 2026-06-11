from django.conf import settings


def normalize_phone(raw):
    """Normalize a phone number to international format '+<dialcode><national>'.

    Accepts numbers in any of these forms and returns a canonical E.164-style
    string (digits with a leading '+'):

        '0716843608'      -> '+27716843608'   (local, leading 0 -> default code)
        '+27 71 684 3608' -> '+27716843608'   (already international)
        '0027716843608'   -> '+27716843608'   ('00' international access prefix)
        '27716843608'     -> '+27716843608'   (already includes country code)

    Empty/blank input returns ''. The default dialling code comes from
    settings.PHONE_DEFAULT_DIAL_CODE (defaults to '27', South Africa).
    """
    if not raw:
        return ''

    s = str(raw).strip()
    has_plus = s.startswith('+')
    digits = ''.join(c for c in s if c.isdigit())
    if not digits:
        return ''

    default_cc = str(getattr(settings, 'PHONE_DEFAULT_DIAL_CODE', '27'))

    if has_plus:
        return '+' + digits
    if digits.startswith('00'):
        return '+' + digits[2:]
    if digits.startswith('0'):
        return '+' + default_cc + digits[1:]
    if digits.startswith(default_cc):
        return '+' + digits
    return '+' + default_cc + digits
