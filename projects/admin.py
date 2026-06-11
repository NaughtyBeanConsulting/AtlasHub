from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    AcceptanceCriterion, Activity, Comment, Issue, Label, Sprint, Status,
)


@admin.register(Status)
class StatusAdmin(ModelAdmin):
    list_display = ['name', 'space', 'category', 'order']
    list_filter = ['space', 'category']
    ordering = ['space', 'order']


@admin.register(Label)
class LabelAdmin(ModelAdmin):
    list_display = ['name', 'space']
    list_filter = ['space']
    search_fields = ['name']


@admin.register(Sprint)
class SprintAdmin(ModelAdmin):
    list_display = ['name', 'space', 'state', 'start_date', 'end_date']
    list_filter = ['space', 'state']


class AcceptanceCriterionInline(TabularInline):
    model = AcceptanceCriterion
    extra = 0


@admin.register(Issue)
class IssueAdmin(ModelAdmin):
    list_display = ['key', 'summary', 'issue_type', 'status', 'priority', 'assignee', 'sprint']
    list_filter = ['space', 'issue_type', 'priority']
    search_fields = ['key', 'summary']
    readonly_fields = ['key', 'number', 'created_at', 'updated_at']
    autocomplete_fields = ['assignee', 'reporter']
    inlines = [AcceptanceCriterionInline]


@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ['issue', 'author', 'created_at']
    search_fields = ['issue__key', 'body_md']


@admin.register(Activity)
class ActivityAdmin(ModelAdmin):
    list_display = ['issue', 'actor', 'field', 'created_at']
    list_filter = ['field']
    search_fields = ['issue__key']
