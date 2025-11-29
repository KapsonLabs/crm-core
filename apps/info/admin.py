from django.contrib import admin
from .models import Category, Tag, FAQ, SOP, PolicyExplanation, TrainingArticle


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id', 'created_at']


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'is_published', 'view_count', 'helpful_count', 'created_at']
    list_filter = ['is_published', 'category', 'created_at']
    search_fields = ['question', 'answer']
    filter_horizontal = ['tags']
    readonly_fields = ['id', 'view_count', 'helpful_count', 'not_helpful_count', 'created_at', 'updated_at', 'published_at']
    fieldsets = (
        ('Content', {
            'fields': ('question', 'answer', 'category', 'tags')
        }),
        ('Status', {
            'fields': ('is_published', 'published_at')
        }),
        ('Statistics', {
            'fields': ('view_count', 'helpful_count', 'not_helpful_count')
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(SOP)
class SOPAdmin(admin.ModelAdmin):
    list_display = ['title', 'version', 'status', 'category', 'is_published', 'view_count', 'created_at']
    list_filter = ['status', 'is_published', 'category', 'created_at']
    search_fields = ['title', 'content']
    filter_horizontal = ['tags']
    readonly_fields = ['id', 'view_count', 'created_at', 'updated_at', 'published_at', 'approved_at']
    fieldsets = (
        ('Content', {
            'fields': ('title', 'content', 'version', 'category', 'tags')
        }),
        ('Status', {
            'fields': ('status', 'is_published', 'published_at', 'approved_by', 'approved_at')
        }),
        ('Statistics', {
            'fields': ('view_count',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(PolicyExplanation)
class PolicyExplanationAdmin(admin.ModelAdmin):
    list_display = ['title', 'policy_reference', 'category', 'is_published', 'view_count', 'created_at']
    list_filter = ['is_published', 'category', 'created_at']
    search_fields = ['title', 'content', 'policy_reference']
    filter_horizontal = ['tags']
    readonly_fields = ['id', 'view_count', 'created_at', 'updated_at', 'published_at']
    fieldsets = (
        ('Content', {
            'fields': ('title', 'content', 'policy_reference', 'category', 'tags')
        }),
        ('Status', {
            'fields': ('is_published', 'published_at')
        }),
        ('Statistics', {
            'fields': ('view_count',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')
        }),
    )


@admin.register(TrainingArticle)
class TrainingArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'difficulty_level', 'estimated_read_time', 'is_published', 'view_count', 'created_at']
    list_filter = ['is_published', 'category', 'difficulty_level', 'created_at']
    search_fields = ['title', 'content', 'summary']
    filter_horizontal = ['tags']
    readonly_fields = ['id', 'view_count', 'created_at', 'updated_at', 'published_at']
    fieldsets = (
        ('Content', {
            'fields': ('title', 'summary', 'content', 'category', 'tags')
        }),
        ('Training Details', {
            'fields': ('difficulty_level', 'estimated_read_time')
        }),
        ('Status', {
            'fields': ('is_published', 'published_at')
        }),
        ('Statistics', {
            'fields': ('view_count',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_by', 'updated_by', 'created_at', 'updated_at')
        }),
    )

