"""Seed a realistic demo: an Atlas project mid-sprint and a wiki space with
mermaid + draw.io content, so every view renders with data.

    python manage.py seed_demo            # fails if demo spaces exist
    python manage.py seed_demo --reset    # delete demo data first
"""
import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Space, SpaceMembership
from projects.models import AcceptanceCriterion, Comment, Issue, Label, Sprint
from projects.services import record_activity
from wiki.models import Diagram, Page, PageComment, PageVersion, unique_slug

DEMO_PASSWORD = 'atlashub-demo'

DEMO_USERS = [
    ('demo@atlashub.local', 'Demo', 'Owner', '+27716840000', True),
    ('thandi@atlashub.local', 'Thandi', 'Mokoena', '+27716840001', False),
    ('pieter@atlashub.local', 'Pieter', 'van Wyk', '', False),
]

SAMPLE_DRAWIO_XML = (
    '<mxfile host="embed.diagrams.net"><diagram name="Page-1">'
    '<mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
    '<mxCell id="2" value="Storefront" style="rounded=1" vertex="1" parent="1">'
    '<mxGeometry x="40" y="40" width="120" height="50" as="geometry"/></mxCell>'
    '<mxCell id="3" value="Django API" style="rounded=1" vertex="1" parent="1">'
    '<mxGeometry x="240" y="40" width="120" height="50" as="geometry"/></mxCell>'
    '<mxCell id="4" style="edgeStyle=orthogonalEdgeStyle" edge="1" parent="1" source="2" target="3">'
    '<mxGeometry relative="1" as="geometry"/></mxCell>'
    '</root></mxGraphModel></diagram></mxfile>'
)

SAMPLE_DRAWIO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="340" height="100">'
    '<rect x="10" y="25" width="120" height="50" rx="6" fill="#DEEBFF" stroke="#0052CC"/>'
    '<text x="70" y="55" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#0747A6">Storefront</text>'
    '<rect x="210" y="25" width="120" height="50" rx="6" fill="#E3FCEF" stroke="#00875A"/>'
    '<text x="270" y="55" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#006644">Django API</text>'
    '<line x1="130" y1="50" x2="210" y2="50" stroke="#42526E" stroke-width="1.5" marker-end="none"/>'
    '</svg>'
)


class Command(BaseCommand):
    help = 'Seed demo data: a CLIC software project mid-sprint + an ENG wiki space.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete existing demo spaces/users first.')

    def handle(self, *args, **options):
        User = get_user_model()

        if options['reset']:
            Space.objects.filter(key__in=['CLIC', 'ENG']).delete()
            User.objects.filter(email__in=[u[0] for u in DEMO_USERS]).delete()
            self.stdout.write('Existing demo data removed.')
        elif Space.objects.filter(key__in=['CLIC', 'ENG']).exists():
            raise CommandError('Demo spaces already exist — run with --reset to recreate.')

        # ── Users ───────────────────────────────────────────────────────────
        users = {}
        for email, first, last, phone, staff in DEMO_USERS:
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(
                    email, DEMO_PASSWORD, first_name=first, last_name=last,
                    phone=phone, is_staff=staff,
                )
            users[first.lower()] = user
        demo, thandi, pieter = users['demo'], users['thandi'], users['pieter']

        # ── Software project ────────────────────────────────────────────────
        clic = Space.objects.create(
            name='Click & Collect', key='CLIC', space_type=Space.TYPE_SOFTWARE,
            description='Order-ahead storefronts for independent coffee shops.',
            color='#0052CC', created_by=demo,
        )
        for user, role in [(demo, 'admin'), (thandi, 'member'), (pieter, 'member')]:
            SpaceMembership.objects.create(space=clic, user=user, role=role)
        statuses = {s.name: s for s in clic.statuses.all()}
        labels = {
            name: Label.objects.create(space=clic, name=name)
            for name in ['payments', 'paystack', 'storefront', 'pwa', 'loyalty']
        }

        def new_issue(**kwargs):
            ac = kwargs.pop('ac', [])
            issue_labels = kwargs.pop('labels', [])
            issue = Issue.objects.create_issue(space=clic, reporter=demo, **kwargs)
            for i, text in enumerate(ac):
                AcceptanceCriterion.objects.create(
                    issue=issue, text=text, order=i, is_done=issue.is_done,
                )
            issue.labels.set([labels[n] for n in issue_labels])
            record_activity(issue, demo, 'created')
            return issue

        billing = new_issue(issue_type='epic', summary='Billing & payments',
                            status=statuses['In Progress'], epic_color='#6554C0')
        storefront = new_issue(issue_type='epic', summary='Storefront experience',
                               status=statuses['In Progress'], epic_color='#0052CC')
        loyalty = new_issue(issue_type='epic', summary='Loyalty programme',
                            status=statuses['To Do'], epic_color='#00875A')

        today = timezone.localdate()
        sprint1 = Sprint.objects.create(
            space=clic, name='CLIC Sprint 1', goal='Take real money safely.',
            state=Sprint.STATE_COMPLETED,
            start_date=today - datetime.timedelta(days=21),
            end_date=today - datetime.timedelta(days=7),
            completed_at=timezone.now() - datetime.timedelta(days=7),
        )
        sprint2 = Sprint.objects.create(
            space=clic, name='CLIC Sprint 2',
            goal='Percentage billing live for the first ten shops.',
            state=Sprint.STATE_ACTIVE,
            start_date=today - datetime.timedelta(days=3),
            end_date=today + datetime.timedelta(days=11),
        )

        # Sprint 1 (completed history)
        new_issue(issue_type='story', summary='Paystack integration for storefront payments',
                  status=statuses['Done'], priority='highest', story_points=8,
                  assignee=thandi, epic=billing, sprint=sprint1,
                  labels=['payments', 'paystack'],
                  description_md='Charge → fallback across stored cards → webhook reconciliation.',
                  ac=['Successful charge activates the account',
                      'Failed charge marks past-due with grace period',
                      'Webhooks are idempotent'])
        new_issue(issue_type='story', summary='Guest checkout for pickup orders',
                  status=statuses['Done'], priority='high', story_points=5,
                  assignee=pieter, epic=storefront, sprint=sprint1, labels=['storefront'],
                  ac=['No account required up to payment', 'Order confirmation over WhatsApp'])

        # Sprint 2 (active board)
        s2 = [
            new_issue(issue_type='story', summary='Percentage billing model (2% per order)',
                      status=statuses['In Progress'], priority='highest', story_points=8,
                      assignee=thandi, epic=billing, sprint=sprint2, labels=['payments'],
                      description_md=(
                          'Bill **2% of order value** monthly instead of a flat fee.\n\n'
                          '```mermaid\ngraph LR;\n  Order --> Ledger;\n  Ledger --> Invoice;\n'
                          '  Invoice --> Paystack;\n```\n'
                          f'Pairing with @[Pieter van Wyk](u:{pieter.pk}) on the ledger.'),
                      ac=['Commission accrues per successful order',
                          'Monthly invoice generated on the 1st',
                          'Failed collection retries across stored cards'], rank=0),
            new_issue(issue_type='task', summary='Reconciliation report for monthly invoices',
                      status=statuses['In Review'], priority='high', story_points=3,
                      assignee=pieter, epic=billing, sprint=sprint2, labels=['payments'], rank=0),
            new_issue(issue_type='story', summary='Scheduled pickup windows',
                      status=statuses['To Do'], priority='medium', story_points=5,
                      assignee=None, epic=storefront, sprint=sprint2, labels=['storefront'],
                      ac=['Shop sets slot capacity per 15 minutes',
                          'Customers see only available slots'], rank=1),
            new_issue(issue_type='bug', summary='PWA icon missing on Android install',
                      status=statuses['Done'], priority='low', story_points=1,
                      assignee=pieter, epic=storefront, sprint=sprint2, labels=['pwa'], rank=0),
        ]
        record_activity(s2[0], thandi, 'status', 'To Do', 'In Progress')
        record_activity(s2[1], pieter, 'status', 'In Progress', 'In Review')
        record_activity(s2[3], pieter, 'status', 'To Do', 'Done')
        story = s2[0]
        for i, st in enumerate(['Write ledger migration', 'Webhook idempotency tests']):
            sub = Issue.objects.create_issue(
                space=clic, issue_type='subtask', summary=st, parent=story,
                status=statuses['Done' if i == 0 else 'In Progress'],
                reporter=thandi, assignee=thandi, epic=billing,
            )
            record_activity(sub, thandi, 'created')
        Comment.objects.create(
            issue=story, author=pieter,
            body_md=f'Ledger schema is in review — @[Thandi Mokoena](u:{thandi.pk}) '
                    'can you double-check the rounding on partial refunds?',
        )
        record_activity(story, pieter, 'comment', '', 'added')

        # Backlog
        new_issue(issue_type='story', summary='Custom domain support for storefronts',
                  status=statuses['To Do'], priority='medium', story_points=5,
                  epic=storefront, labels=['storefront'], rank=0,
                  ac=['CNAME verification flow', 'Automatic TLS'])
        new_issue(issue_type='story', summary='Save favourite drink configurations',
                  status=statuses['To Do'], priority='low', story_points=3,
                  epic=loyalty, labels=['loyalty'], rank=0)
        new_issue(issue_type='story', summary='Loyalty points earned per order',
                  status=statuses['To Do'], priority='medium', story_points=5,
                  epic=loyalty, labels=['loyalty'], rank=1,
                  ac=['1 point per R10', 'Redemption at checkout'])
        new_issue(issue_type='bug', summary='WhatsApp numbers not internationalised for non-ZA shops',
                  status=statuses['To Do'], priority='high', story_points=2,
                  epic=None, labels=['storefront'], rank=0)

        # ── Wiki space ──────────────────────────────────────────────────────
        eng = Space.objects.create(
            name='Engineering Docs', key='ENG', space_type=Space.TYPE_WIKI,
            description='How we build and run Click & Collect.',
            color='#00875A', created_by=demo,
        )
        for user, role in [(demo, 'admin'), (thandi, 'member'), (pieter, 'member')]:
            SpaceMembership.objects.create(space=eng, user=user, role=role)

        def new_page(title, body, parent=None, position=0, author=demo):
            page = Page.objects.create(
                space=eng, parent=parent, title=title,
                slug=unique_slug(eng, title), body_md=body, position=position,
                created_by=author, updated_by=author,
            )
            PageVersion.objects.create(page=page, number=1, title=title,
                                       body_md=body, edited_by=author)
            return page

        welcome = new_page('Welcome', (
            '# Welcome to Engineering Docs\n\n'
            'Everything about how we build **Click & Collect** lives here.\n\n'
            '- [Architecture](architecture) — systems and how they talk\n'
            '- [Runbooks](runbooks) — operational checklists\n'
        ))
        architecture = new_page('Architecture', (
            'High-level view of the platform:\n\n'
            '```mermaid\ngraph TD;\n  Customer((Customer)) --> PWA[Storefront PWA];\n'
            '  PWA --> API[Django API];\n  API --> DB[(PostgreSQL)];\n'
            '  API --> Paystack;\n  API --> WA[WhatsApp worker];\n```\n\n'
            'The block diagram below is editable in place (draw.io):\n\n'
        ), position=1)
        diagram = Diagram.objects.create(
            page=architecture, title='Service map',
            xml=SAMPLE_DRAWIO_XML, svg=SAMPLE_DRAWIO_SVG,
        )
        architecture.body_md += f'{diagram.fence}\n'
        architecture.save(update_fields=['body_md'])
        new_page('Payments flow', (
            '```mermaid\nsequenceDiagram;\n  Customer->>API: Pay order;\n'
            '  API->>Paystack: Charge stored card;\n  Paystack-->>API: Webhook (success);\n'
            '  API->>Customer: WhatsApp confirmation;\n```\n\n'
            'Charges fall back across stored cards; webhooks reconcile final state.'
        ), parent=architecture)
        runbooks = new_page('Runbooks', 'Operational checklists for the platform.', position=2)
        new_page('Deploy checklist', (
            '1. `./build_tailwind.sh`\n2. `python manage.py migrate`\n'
            '3. `python manage.py collectstatic`\n4. Restart gunicorn + the WhatsApp worker\n'
        ), parent=runbooks)
        new_page('WhatsApp worker recovery', (
            'If the queue stalls:\n\n'
            '- Check `/whatsapp/` for the connection state\n'
            '- `systemctl restart atlashub-whatsapp-worker`\n'
            '- Re-pair from **/whatsapp/link/** if the session was logged out\n'
        ), parent=runbooks, position=1)
        PageComment.objects.create(
            page=welcome, author=thandi,
            body_md=f'@[Demo Owner](u:{demo.pk}) shall we add the billing docs here too?',
        )

        self.stdout.write(self.style.SUCCESS(
            'Demo data created.\n'
            f'  Atlas:        /projects/CLIC/  (board mid-sprint, backlog, timeline)\n'
            f'  Hub:  /wiki/ENG/\n'
            f'  Log in as    demo@atlashub.local / {DEMO_PASSWORD}  (staff)\n'
            f'               thandi@atlashub.local / {DEMO_PASSWORD}\n'
            f'               pieter@atlashub.local / {DEMO_PASSWORD}'
        ))
