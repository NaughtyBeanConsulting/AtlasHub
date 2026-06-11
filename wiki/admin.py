from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Diagram, Page, PageComment, PageVersion


@admin.register(Page)
class PageAdmin(ModelAdmin):
    list_display = ['title', 'space', 'parent', 'position', 'updated_at']
    list_filter = ['space']
    search_fields = ['title', 'slug']
    readonly_fields = ['slug']


@admin.register(PageVersion)
class PageVersionAdmin(ModelAdmin):
    list_display = ['page', 'number', 'edited_by', 'created_at']
    search_fields = ['page__title']


@admin.register(Diagram)
class DiagramAdmin(ModelAdmin):
    list_display = ['title', 'page', 'updated_at']
    search_fields = ['title', 'page__title']


@admin.register(PageComment)
class PageCommentAdmin(ModelAdmin):
    list_display = ['page', 'author', 'created_at']
    search_fields = ['page__title', 'body_md']
