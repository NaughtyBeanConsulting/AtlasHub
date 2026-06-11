from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Space, SpaceMembership


class SpaceMembershipInline(TabularInline):
    model = SpaceMembership
    extra = 0
    autocomplete_fields = ['user']


@admin.register(Space)
class SpaceAdmin(ModelAdmin):
    list_display = ['key', 'name', 'space_type', 'created_by', 'created_at']
    list_filter = ['space_type']
    search_fields = ['key', 'name']
    inlines = [SpaceMembershipInline]


@admin.register(SpaceMembership)
class SpaceMembershipAdmin(ModelAdmin):
    list_display = ['space', 'user', 'role', 'added_at']
    list_filter = ['role', 'space']
    search_fields = ['user__email', 'space__key']
